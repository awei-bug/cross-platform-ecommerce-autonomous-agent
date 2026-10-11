"""Production-mode smoke test for the local PostgreSQL + Celery stack.

This script deliberately exercises only the currently implemented, explicitly marked
Demo flows. It never calls a real marketplace API and it does not claim that platform
synchronization is enabled.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from uuid import uuid4

import httpx


@dataclass(frozen=True)
class SmokeContext:
    client: httpx.Client
    headers: dict[str, str]
    timeout_seconds: float


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="验收本地生产模式 API、PostgreSQL 与单进程（eager）任务链路"
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("SMOKE_BASE_URL", "http://127.0.0.1:8001"),
        help="生产模式 API 地址，默认读取 SMOKE_BASE_URL 或 http://127.0.0.1:8001",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="异步任务最长等待秒数，默认 30",
    )
    return parser.parse_args()


def _check(label: str, condition: bool, detail: str) -> None:
    if not condition:
        raise RuntimeError(f"{label} 失败：{detail}")
    print(f"[通过] {label}：{detail}")


def _request(
    context: SmokeContext,
    method: str,
    path: str,
    *,
    expected_status: int = 200,
    **kwargs: object,
) -> httpx.Response:
    response = context.client.request(method, path, headers=context.headers, **kwargs)
    _check(
        f"HTTP {method} {path}",
        response.status_code == expected_status,
        f"状态码 {response.status_code}",
    )
    return response


def _wait_for_job(
    context: SmokeContext,
    path: str,
    *,
    expected_statuses: set[str],
) -> dict[str, object]:
    deadline = time.monotonic() + context.timeout_seconds
    last_payload: dict[str, object] = {}
    while time.monotonic() < deadline:
        response = _request(context, "GET", path)
        last_payload = response.json()
        status = str(last_payload.get("status"))
        if status in {"queued", "running"}:
            time.sleep(0.5)
            continue
        _check(
            f"异步任务 {path}",
            status in expected_statuses,
            f"最终状态 {status}，进度 {last_payload.get('progress')}%",
        )
        _check(
            f"异步任务 {path} 持久化结果",
            last_payload.get("progress") == 100,
            f"成功 {last_payload.get('succeeded')}，失败 {last_payload.get('failed')}",
        )
        return last_payload
    raise TimeoutError(f"异步任务超时：{path}，最后状态 {last_payload.get('status')}")


def _run(base_url: str, timeout_seconds: float) -> None:
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=10.0) as client:
        health = client.get("/health")
        _check("API 存活检查", health.status_code == 200, f"状态码 {health.status_code}")

        ready = client.get("/ready")
        _check("生产就绪检查", ready.status_code == 200, f"状态码 {ready.status_code}")
        ready_payload = ready.json()
        _check(
            "生产执行模式",
            ready_payload.get("task_execution") == "eager",
            (
                f"数据库 {ready_payload.get('database')}，"
                f"任务模式 {ready_payload.get('task_execution')}"
            ),
        )

        login = client.post(
            "/api/v1/auth/login",
            json={"account": "demo", "password": "demo1234"},
        )
        _check("演示账号登录", login.status_code == 200, f"状态码 {login.status_code}")
        token = login.json().get("access_token")
        _check("登录令牌", isinstance(token, str) and bool(token), "已取得访问令牌")

        context = SmokeContext(
            client=client,
            headers={"Authorization": f"Bearer {token}"},
            timeout_seconds=timeout_seconds,
        )

        providers = _request(context, "GET", "/api/v1/ai/providers").json()
        _check(
            "AI 厂商目录读取",
            any(item.get("id") == "mock" for item in providers),
            f"返回 {len(providers)} 个厂商，未调用真实模型",
        )
        configurations = _request(context, "GET", "/api/v1/ai/configurations").json()
        config_items = configurations.get("items", [])
        mock_config = next(
            (item for item in config_items if item.get("provider_id") == "mock"),
            None,
        )
        if mock_config is None:
            mock_config = _request(
                context,
                "POST",
                "/api/v1/ai/configurations",
                expected_status=201,
                json={
                    "provider_id": "mock",
                    "display_name": "生产烟囱演示配置",
                },
            ).json()
        _check("AI 配置持久化", mock_config.get("is_demo") is True, mock_config["id"])
        tested = _request(
            context,
            "POST",
            f"/api/v1/ai/configurations/{mock_config['id']}/test",
        ).json()
        _check(
            "AI 模型发现",
            tested.get("status") == "connected" and len(tested.get("models", [])) >= 3,
            f"发现 {len(tested.get('models', []))} 个演示模型",
        )
        selected = _request(
            context,
            "PATCH",
            f"/api/v1/ai/configurations/{mock_config['id']}",
            json={"selected_model": "demo-copy-v1"},
        ).json()
        generation_job = _request(
            context,
            "POST",
            "/api/v1/assets/generation-jobs",
            expected_status=202,
            json={
                "asset_type": "copy",
                "prompt": "生产烟囱测试：生成一条春季保湿面霜候选文案",
                "configuration_id": selected["id"],
                "model_id": "demo-copy-v1",
            },
        ).json()
        generation_final = _wait_for_job(
            context,
            f"/api/v1/assets/generation-jobs/{generation_job['id']}",
            expected_statuses={"succeeded"},
        )
        _check(
            "素材 AI 生成任务链路",
            generation_final.get("is_demo") is True
            and bool(generation_final.get("result_version_id"))
            and bool(generation_final.get("asset_id")),
            "AI Provider → PostgreSQL → 单进程任务执行 → 素材版本",
        )
        confirmed = _request(
            context,
            "POST",
            f"/api/v1/assets/{generation_final['asset_id']}/versions/{generation_final['result_version_id']}/confirm",
        ).json()
        _check(
            "素材人工确认边界",
            confirmed.get("status") == "approved"
            and confirmed.get("current_version_id") == generation_final["result_version_id"],
            "已确认入库，未自动发布或覆盖线上素材",
        )

        connectors = _request(context, "GET", "/api/v1/integrations/connectors").json()
        _check(
            "平台连接状态读取",
            isinstance(connectors, list) and len(connectors) >= 1,
            f"返回 {len(connectors)} 个连接器状态",
        )

        products = _request(
            context,
            "GET",
            "/api/v1/products",
            params={"shop_id": "shop-all", "page": 1, "page_size": 10},
        ).json()
        product_items = products.get("items", [])
        _check(
            "商品主数据读取",
            products.get("is_demo") is True and bool(product_items),
            f"演示数据，返回 {len(product_items)} 个商品",
        )

        product_id = product_items[0]["id"]
        product_job = _request(
            context,
            "POST",
            "/api/v1/products/batch-actions",
            expected_status=202,
            json={
                "action": "sync",
                "product_ids": [product_id],
                "payload": {},
                "idempotency_key": f"production-smoke-product-{uuid4().hex}",
            },
        ).json()
        _check(
            "商品异步任务创建",
            product_job.get("status") in {"queued", "succeeded"},
            str(product_job["id"]),
        )
        product_final = _wait_for_job(
            context,
            f"/api/v1/products/jobs/{product_job['id']}",
            expected_statuses={"succeeded"},
        )
        _check(
            "商品任务执行链路",
            product_final.get("is_demo") is True and product_final.get("succeeded") == 1,
            "API → PostgreSQL → 单进程任务执行 → PostgreSQL",
        )

        orders = _request(
            context,
            "GET",
            "/api/v1/orders",
            params={"shop_id": "shop-all", "page": 1, "page_size": 10},
        ).json()
        order_items = orders.get("items", [])
        _check(
            "订单主数据读取",
            orders.get("is_demo") is True and len(order_items) >= 3,
            f"演示数据，返回 {len(order_items)} 个订单",
        )
        order_ids = [item["id"] for item in order_items[:3]]
        order_job = _request(
            context,
            "POST",
            "/api/v1/orders/actions",
            expected_status=202,
            json={
                "action": "remind_ship",
                "order_ids": order_ids,
                "payload": {"source": "production-smoke"},
                "idempotency_key": f"production-smoke-order-{uuid4().hex}",
            },
        ).json()
        order_final = _wait_for_job(
            context,
            f"/api/v1/orders/jobs/{order_job['id']}",
            expected_statuses={"partial", "succeeded"},
        )
        _check(
            "订单任务执行链路",
            order_final.get("is_demo") is True and int(order_final.get("succeeded", 0)) >= 2,
            (
                f"最终状态 {order_final.get('status')}，"
                f"成功 {order_final.get('succeeded')}，失败 {order_final.get('failed')}"
            ),
        )

        audit = _request(
            context,
            "GET",
            "/api/v1/orders/audit",
            params={"order_id": order_ids[0]},
        ).json()
        _check(
            "订单审计持久化",
            any(entry.get("is_demo") is True for entry in audit),
            f"订单 {order_ids[0]} 返回 {len(audit)} 条审计记录",
        )

        alerts = _request(context, "GET", "/api/v1/workspace/alerts").json()
        _check(
            "告警状态读取",
            isinstance(alerts, list) and bool(alerts),
            f"返回 {len(alerts)} 条告警",
        )
        alert = alerts[0]
        original_is_read = bool(alert.get("is_read"))
        alert_id = alert["id"]
        updated = _request(
            context,
            "PATCH",
            f"/api/v1/workspace/alerts/{alert_id}",
            json={"is_read": not original_is_read},
        ).json()
        _check(
            "告警已读状态写入",
            updated.get("is_read") is (not original_is_read),
            f"告警 {alert_id} 已切换为 {updated.get('is_read')}",
        )
        restored = _request(
            context,
            "PATCH",
            f"/api/v1/workspace/alerts/{alert_id}",
            json={"is_read": original_is_read},
        ).json()
        _check(
            "告警已读状态恢复",
            restored.get("is_read") is original_is_read,
            f"告警 {alert_id} 恢复为 {original_is_read}",
        )

        print(
            "\n生产模式验收通过：已验证 AI 配置、模型发现、素材生成和人工确认边界；"
            "真实模型与平台仍未自动调用。"
        )


def main() -> int:
    args = _parse_args()
    try:
        _run(args.base_url, args.timeout)
    except (httpx.HTTPError, KeyError, RuntimeError, TimeoutError) as exc:
        print(f"[失败] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
