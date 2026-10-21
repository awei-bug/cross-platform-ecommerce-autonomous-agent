"""淘宝客公开商品数据源适配层（阿里妈妈 / 淘宝开放平台）。

与卖家店铺 API 不同，淘宝客接口不需要店铺授权：个人实名开发者即可申请
（淘宝联盟实名 → 媒体备案 → 推广位 PID → 开放平台应用），凭
AppKey + AppSecret + adzone_id 调用 TOP 网关，获取公开商品数据
（标题、价格、销量、优惠券、佣金），用于竞品情报检索。

使用边界（README「竞品数据源」一节有完整说明）：
- 权限与备案的媒体渠道绑定，数据用途以阿里妈妈规则为准；
- 连续 30 天无调用量或成交量，平台可能回收 API 权限；
- 高级接口（链接转换等）为邀请制，此处只用公开的基础商品检索能力。
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

SHANGHAI = ZoneInfo("Asia/Shanghai")

MATERIAL_SEARCH_METHOD = "taobao.tbk.dg.material.optional"


class TaobaokeApiError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        sub_code: str | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.sub_code = sub_code
        self.retryable = retryable


class TaobaokeNotConfigured(TaobaokeApiError):
    """凭证缺失时抛出，调用方应如实提示配置路径，不做任何伪造数据。"""


@dataclass(frozen=True)
class TaobaokeMaterial:
    item_id: str
    title: str
    price: float
    reserve_price: float | None
    coupon_amount: float | None
    sales_volume: int
    commission_rate: float | None
    shop_title: str | None
    category_name: str | None
    is_tmall: bool
    item_url: str | None


def sign_top_request(parameters: dict[str, str], app_secret: str) -> str:
    """TOP 网关 MD5 签名。

    规范：除 sign 外全部参数按 key 升序拼接 key+value，得到串 S，
    对 app_secret + S + app_secret 取 MD5 并转大写。
    注意与抖店签名的差异：淘宝是在首尾都包 secret，抖店只在末尾追加。
    """
    canonical = "".join(f"{key}{parameters[key]}" for key in sorted(parameters))
    payload = f"{app_secret}{canonical}{app_secret}".encode()
    return hashlib.md5(payload).hexdigest().upper()  # noqa: S324 - TOP 网关强制 MD5


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int:
    if value is None or value == "":
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _parse_commission_rate(value: Any) -> float | None:
    """佣金比率归一为百分比。

    不同接口/时期的字段单位不一致（如 1500 表示万分位，或 15.0 表示百分比），
    大于 100 时按万分位换算，否则按原值解释。
    """
    parsed = _to_float(value)
    if parsed is None:
        return None
    if parsed > 100:
        return round(parsed / 100, 2)
    return round(parsed, 2)


def parse_materials(payload: dict[str, Any]) -> list[TaobaokeMaterial]:
    """解析物料搜索响应；错误响应如实抛出。"""
    error = payload.get("error_response")
    if isinstance(error, dict):
        message = error.get("sub_msg") or error.get("msg") or "淘宝客接口返回错误"
        raise TaobaokeApiError(
            str(message),
            code=str(error.get("code")) if error.get("code") is not None else None,
            sub_code=str(error.get("sub_code")) if error.get("sub_code") else None,
        )
    response: dict[str, Any] | None = None
    for key, value in payload.items():
        if key.endswith("_response") and isinstance(value, dict):
            response = value
            break
    if response is None:
        raise TaobaokeApiError("淘宝客响应格式无法识别（缺少 *_response 节点）")
    result_list = response.get("result_list")
    rows: Any = result_list.get("map_data") if isinstance(result_list, dict) else None
    if rows is None:
        rows = response.get("map_data") or []
    if not isinstance(rows, list):
        raise TaobaokeApiError("淘宝客响应中的商品列表格式无法识别")
    materials: list[TaobaokeMaterial] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        item_id = row.get("item_id")
        title = row.get("title")
        if item_id is None or not title:
            continue
        final_price = _to_float(row.get("zk_final_price"))
        reserve_price = _to_float(row.get("reserve_price"))
        price = final_price if final_price is not None else (reserve_price or 0.0)
        materials.append(
            TaobaokeMaterial(
                item_id=str(item_id),
                title=str(title)[:200],
                price=round(price, 2),
                reserve_price=round(reserve_price, 2) if reserve_price is not None else None,
                coupon_amount=_to_float(row.get("coupon_amount")),
                sales_volume=_to_int(row.get("volume")),
                commission_rate=_parse_commission_rate(row.get("commission_rate")),
                shop_title=row.get("shop_title") or None,
                category_name=row.get("category_name") or None,
                is_tmall=str(row.get("user_type")) == "1",
                item_url=row.get("item_url") or None,
            )
        )
    return materials


class TaobaokeClient:
    def __init__(
        self,
        *,
        app_key: str,
        app_secret: str,
        adzone_id: str,
        api_base_url: str,
        timeout_seconds: float = 10.0,
        max_attempts: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.app_key = app_key
        self.app_secret = app_secret
        self.adzone_id = adzone_id
        self.api_base_url = api_base_url
        self.timeout = httpx.Timeout(timeout_seconds)
        self.max_attempts = max(1, max_attempts)
        self.transport = transport

    def build_parameters(self, method: str, business: dict[str, str]) -> dict[str, str]:
        parameters: dict[str, str] = {
            "method": method,
            "app_key": self.app_key,
            "timestamp": datetime.now(SHANGHAI).strftime("%Y-%m-%d %H:%M:%S"),
            "format": "json",
            "v": "2.0",
            "sign_method": "md5",
        }
        parameters.update(business)
        parameters["sign"] = sign_top_request(parameters, self.app_secret)
        return parameters

    async def search_materials(
        self,
        *,
        keyword: str,
        page_no: int = 1,
        page_size: int = 20,
        sort: str | None = None,
    ) -> list[TaobaokeMaterial]:
        """关键词物料搜索（taobao.tbk.dg.material.optional），返回公开商品列表。"""
        business: dict[str, str] = {
            "adzone_id": self.adzone_id,
            "q": keyword,
            "page_no": str(max(1, page_no)),
            "page_size": str(min(max(1, page_size), 40)),
        }
        if sort:
            business["sort"] = sort
        parameters = self.build_parameters(MATERIAL_SEARCH_METHOD, business)
        payload = await self._request(parameters, max_attempts=self.max_attempts)
        return parse_materials(payload)

    async def _request(
        self, parameters: dict[str, str], *, max_attempts: int
    ) -> dict[str, Any]:
        attempts = max(1, max_attempts)
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout,
                    transport=self.transport,
                    follow_redirects=False,
                ) as client:
                    response = await client.post(self.api_base_url, data=parameters)
                if response.status_code >= 500:
                    if attempt + 1 < attempts:
                        await asyncio.sleep(0.2 * (2**attempt))
                        continue
                    raise TaobaokeApiError(
                        f"淘宝客服务暂时不可用（HTTP {response.status_code}）",
                        retryable=True,
                    )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise TaobaokeApiError("淘宝客服务返回了非对象 JSON")
                return payload
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.2 * (2**attempt))
                    continue
            except (httpx.HTTPStatusError, ValueError) as exc:
                raise TaobaokeApiError("淘宝客服务返回了无法处理的响应") from exc
        raise TaobaokeApiError("连接淘宝客服务超时或网络不可用", retryable=True) from last_error
