"""商品记忆库（data-hub）只读客户端。

设计原则
- **只读**：本项目是消费者，不写 data-hub。唯一写入方是内容平台（ingest），
  电商侧负责 ack，其余项目一律 GET。
- **降级不阻断**：未配置 DATA_HUB_URL、网络失败、返回非预期结构，一律由调用方
  拿到空结果，不影响商品中心、订单售后、抖店同步等既有链路。
- **不编造**：远端没有的字段就是不返回，不用本地默认值补齐。

与电商项目 `flask_shop/utils/hub_client.py` 的关系：两边都只读同一个 data-hub，
接口与鉴权头一致（`X-Hub-Tenant` / `X-Hub-Token`），但本项目不实现 ack——
上架回执由电商侧负责，这里重复实现只会产生第二个真相。
"""
from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.core.config import Settings, get_settings


class HubError(RuntimeError):
    """data-hub 不可用或返回错误。"""


def hub_enabled(settings: Settings | None = None) -> bool:
    """是否配置了可用的 data-hub 连接。"""
    cfg = settings or get_settings()
    return bool(cfg.data_hub_url and cfg.data_hub_tenant_slug)


def _config(settings: Settings | None = None) -> dict[str, Any]:
    cfg = settings or get_settings()
    return {
        "url": (cfg.data_hub_url or "").rstrip("/"),
        "token": cfg.data_hub_token or "",
        "tenant": cfg.data_hub_tenant_slug or "",
        "timeout": float(cfg.data_hub_timeout_seconds or 10.0),
    }


def _headers(settings: Settings | None = None) -> dict[str, str]:
    cfg = _config(settings)
    headers = {"Accept": "application/json"}
    if cfg["tenant"]:
        headers["X-Hub-Tenant"] = cfg["tenant"]
    if cfg["token"]:
        headers["X-Hub-Token"] = cfg["token"]
    return headers


def _client(settings: Settings | None = None) -> httpx.Client | None:
    cfg = _config(settings)
    if not cfg["url"]:
        return None
    return httpx.Client(
        base_url=cfg["url"],
        headers=_headers(settings),
        timeout=cfg["timeout"],
    )


def _request(
    method: str, path: str, *, settings: Settings | None = None, body: dict | None = None
) -> dict[str, Any]:
    cfg = _config(settings)
    if not cfg["url"]:
        raise HubError("未配置 DATA_HUB_URL")
    max_attempts = max(1, int((settings or get_settings()).data_hub_http_max_attempts))
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            with _client(settings) as client:
                response = client.request(method, path, json=body)
            if response.status_code >= 400:
                raise HubError(f"data-hub 返回 {response.status_code}: {response.text[:200]}")
            payload = response.json()
            if not isinstance(payload, dict):
                raise HubError("data-hub 响应不是 JSON 对象")
            return payload
        except HubError:
            raise
        except Exception as exc:  # 网络层错误才重试
            last_error = exc
            if attempt >= max(1, int((settings or get_settings()).data_hub_http_max_attempts)):
                break
    raise HubError(f"data-hub 连接失败：{last_error}")


def fetch_product_knowledge(
    external_id: str, *, settings: Settings | None = None
) -> dict[str, Any] | None:
    """按 external_id 拉取商品内容知识（卖点 / 场景 / 规格 / FAQ / 图片）。

    data-hub 没有该记录时返回 None，由调用方决定降级为什么，这里不补默认值。
    """
    cfg = _config(settings)
    if not cfg["url"] or not external_id:
        return None
    try:
        payload = _request(
            "GET",
            f"/hub/products/{cfg['tenant']}/{external_id}",
            settings=settings,
        )
    except HubError:
        return None
    item = payload.get("item")
    return item if isinstance(item, dict) else None


def search_product_knowledge(
    query: str, *, limit: int = 5, settings: Settings | None = None
) -> list[dict[str, Any]]:
    """关键词检索商品知识卡，供 AI 建议与客服口径使用。"""
    cfg = _config(settings)
    if not cfg["url"] or not query.strip():
        return []
    try:
        payload = _request(
            "POST",
            "/hub/search",
            settings=settings,
            body={
                "tenant_slug": cfg["tenant"],
                "query": query,
                "limit": max(1, min(int(limit), 20)),
                "published_only": True,
            },
        )
    except HubError:
        return []
    cards = payload.get("cards")
    return [card for card in cards if isinstance(card, dict)] if isinstance(cards, list) else []


def list_product_knowledge(
    *, status: str = "", limit: int = 50, settings: Settings | None = None
) -> list[dict[str, Any]]:
    """列出商品知识记录。仅用于数据中台导入与对账，不参与运行时热路径。"""
    cfg = _config(settings)
    if not cfg["url"]:
        return []
    path = f"/hub/products?tenant={cfg['tenant']}&limit={max(1, min(int(limit), 500))}"
    if status:
        path += f"&status={status}"
    try:
        payload = _request("GET", path, settings=settings)
    except HubError:
        return []
    items = payload.get("items")
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def health(*, settings: Settings | None = None) -> dict[str, Any] | None:
    """data-hub 健康检查。未配置或不可用时返回 None，不抛异常。"""
    if not hub_enabled(settings):
        return None
    try:
        return _request("GET", "/health", settings=settings)
    except HubError:
        return None


async def fetch_product_knowledge_async(
    external_id: str, *, settings: Settings | None = None
) -> dict[str, Any] | None:
    """异步版本：供已在事件循环中的路由直接 await，避免嵌套 asyncio.run。"""
    cfg = _config(settings)
    if not cfg["url"] or not external_id:
        return None
    try:
        async with httpx.AsyncClient(
            base_url=cfg["url"], headers=_headers(settings), timeout=cfg["timeout"]
        ) as client:
            response = await client.get(f"/hub/products/{cfg['tenant']}/{external_id}")
    except Exception:
        return None
    if response.status_code >= 400:
        return None
    try:
        payload = response.json()
    except Exception:
        return None
    item = payload.get("item") if isinstance(payload, dict) else None
    return item if isinstance(item, dict) else None


def run_fetch_sync(external_id: str, *, settings: Settings | None = None) -> dict[str, Any] | None:
    """同步包装：Celery eager 等无事件循环场景使用。

    已在事件循环内不要调用它——会嵌套 asyncio.run。那种场景用
    `fetch_product_knowledge_async`。
    """
    return asyncio.run(fetch_product_knowledge_async(external_id, settings=settings))
