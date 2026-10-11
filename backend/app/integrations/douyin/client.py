"""抖店开放平台（op.jinritemai.com）适配层。

抖店商家授权复用抖音 OAuth 授权页（client_key），Token 与业务 API 调用统一走
openapi-fxg.jinritemai.com 的 TOP 风格网关：app_key + method + param_json +
timestamp + v + sign（抖店通用 MD5 签名）。抖店开放平台为开发者提供官方测试店铺，
因此无需自有店铺即可拿到真实 access_token 联调（详见 connectors 文档）。
"""

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx


class DouyinApiError(RuntimeError):
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


@dataclass(frozen=True)
class DouyinToken:
    access_token: str
    refresh_token: str | None
    access_token_expires_at: datetime | None
    refresh_token_expires_at: datetime | None
    shop_id: str | None
    shop_name: str | None
    scopes: list[str]


@dataclass(frozen=True)
class SellerIdentity:
    user_id: str
    user_name: str
    shop_id: str | None
    shop_name: str | None


def sign_douyin_request(parameters: dict[str, str], app_secret: str) -> str:
    """抖店通用签名：除 sign 外参数按 key 升序拼接 key+value，末尾追加 app_secret，MD5 大写。"""
    canonical = "".join(f"{key}{parameters[key]}" for key in sorted(parameters))
    payload = f"{canonical}{app_secret}".encode()
    return hashlib.md5(payload).hexdigest().upper()  # noqa: S324 - 抖店强制 MD5


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise DouyinApiError("抖店响应中的有效期不是有效秒数") from exc


def _seconds_to_expiry(now: datetime, seconds: int | None) -> datetime | None:
    return now + timedelta(seconds=seconds) if seconds is not None else None


class DouyinClient:
    def __init__(
        self,
        *,
        app_key: str,
        app_secret: str,
        redirect_uri: str,
        auth_base_url: str,
        token_base_url: str,
        api_base_url: str,
        timeout_seconds: float = 10.0,
        max_attempts: int = 3,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.app_key = app_key
        self.app_secret = app_secret
        self.redirect_uri = redirect_uri
        self.auth_base_url = auth_base_url.rstrip("/")
        self.token_base_url = token_base_url.rstrip("/")
        self.api_base_url = api_base_url.rstrip("/")
        self.timeout = httpx.Timeout(timeout_seconds)
        self.max_attempts = max(1, max_attempts)
        self.transport = transport

    def build_authorization_url(self, state: str, scope: str = "shop.order,shop.product") -> str:
        # 抖店商家授权复用抖音 OAuth 授权页，凭据字段名为 client_key。
        query = urlencode(
            {
                "client_key": self.app_key,
                "response_type": "code",
                "scope": scope,
                "redirect_uri": self.redirect_uri,
                "state": state,
            }
        )
        return f"{self.auth_base_url}/?{query}"

    async def exchange_code(self, code: str) -> DouyinToken:
        """用授权 code 换 Token（工具型应用 / 商家授权页跳转场景）。"""
        return await self._request_token({"grant_type": "authorization_code", "code": code})

    async def exchange_shop_id(self, shop_id: str) -> DouyinToken:
        """自用型应用直接用测试店铺 ID 换 Token。

        抖店「测试账号管理」对自用型应用给出的是【店铺 id】并说明其用于换取
        access_token；该分支按同一接口传 shop_id。若平台侧不接受，错误会如实抛出。
        """
        return await self._request_token(
            {"grant_type": "authorization_code", "shop_id": str(shop_id)}
        )

    async def refresh_token(self, refresh_token: str) -> DouyinToken:
        return await self._request_token(
            {"grant_type": "refresh_token", "refresh_token": refresh_token}
        )

    async def _request_token(self, grant_params: dict[str, str]) -> DouyinToken:
        is_create = grant_params.get("grant_type") == "authorization_code"
        method = "token.create" if is_create else "token.refresh"
        param_json = json.dumps(grant_params, separators=(",", ":"), ensure_ascii=False)
        params = {
            "app_key": self.app_key,
            "method": method,
            "param_json": param_json,
            "timestamp": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
            "v": "2",
            "sign_method": "md5",
        }
        params["sign"] = sign_douyin_request(params, self.app_secret)
        endpoint = "token/create" if is_create else "token/refresh"
        payload = await self._request(
            "GET",
            f"{self.token_base_url}/{endpoint}",
            params=params,
            max_attempts=1,
        )
        return self._parse_token(payload)

    def _parse_token(self, payload: dict[str, Any]) -> DouyinToken:
        data = payload.get("data", payload)
        access_token = data.get("access_token") or payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise DouyinApiError(payload.get("message") or "抖店 Token 响应缺少 access_token")
        now = datetime.now(UTC)
        shop_id = (
            data.get("shop_id") if data.get("shop_id") is not None else payload.get("shop_id")
        )
        shop_name = (
            data.get("shop_name")
            if data.get("shop_name") is not None
            else payload.get("shop_name")
        )
        return DouyinToken(
            access_token=access_token,
            refresh_token=data.get("refresh_token") or payload.get("refresh_token"),
            access_token_expires_at=_seconds_to_expiry(
                now, _coerce_int(data.get("expires_in") or payload.get("expires_in"))
            ),
            refresh_token_expires_at=_seconds_to_expiry(
                now,
                _coerce_int(
                    data.get("refresh_expires_in") or payload.get("refresh_expires_in")
                ),
            ),
            shop_id=str(shop_id) if shop_id is not None else None,
            shop_name=shop_name,
            scopes=[],
        )

    async def fetch_seller_identity(self, access_token: str) -> SellerIdentity:
        payload = await self.call_api("shop.getShopInfo", access_token)
        shop = (
            payload.get("shop_info")
            if isinstance(payload.get("shop_info"), dict)
            else payload
        )
        if not isinstance(shop, dict):
            raise DouyinApiError("抖店店铺信息响应缺少 shop_info")
        shop_id = shop.get("shop_id") or shop.get("open_id")
        shop_name = shop.get("shop_name")
        if shop_id is None:
            raise DouyinApiError("抖店店铺信息响应缺少 shop_id")
        return SellerIdentity(
            user_id=str(shop_id),
            user_name=str(shop_name) if shop_name is not None else str(shop_id),
            shop_id=str(shop_id),
            shop_name=str(shop_name) if shop_name is not None else None,
        )

    async def call_api(
        self, method: str, access_token: str, **business_parameters: Any
    ) -> dict[str, Any]:
        param_json = json.dumps(business_parameters, separators=(",", ":"), ensure_ascii=False)
        params = {
            "app_key": self.app_key,
            "method": method,
            "param_json": param_json,
            "timestamp": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
            "v": "2",
            "sign_method": "md5",
            "access_token": access_token,
        }
        params["sign"] = sign_douyin_request(params, self.app_secret)
        payload = await self._request(
            "POST",
            f"{self.api_base_url}/",
            data=params,
            max_attempts=self.max_attempts,
        )
        err_no = payload.get("err_no")
        if err_no is not None and err_no != 0:
            message = payload.get("message") or "抖店 API 调用失败"
            raise DouyinApiError(str(message), code=str(err_no))
        return payload.get("data", payload)

    # ------------------------------------------------------------------
    # 真实业务 API（商品）
    # 抖店商品价格单位为「分」，对外统一折算为「元」。
    # ------------------------------------------------------------------
    async def list_products(
        self,
        access_token: str,
        *,
        page: int = 1,
        size: int = 20,
        status: int | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """拉取店铺商品列表，返回 (商品列表, 总数)。

        对应开放平台 `product.listV2`（批量查询商品列表，新版）。
        status: 0-在线；1-下线；2-删除；None 表示不限。
        """
        request: dict[str, Any] = {"page": page, "size": size}
        if status is not None:
            request["status"] = status
        payload = await self.call_api("product.listV2", access_token, **request)
        container = payload if isinstance(payload, dict) else {}
        rows = (
            container.get("products")
            or container.get("list")
            or container.get("product_list")
            or []
        )
        if not isinstance(rows, list):
            raise DouyinApiError("抖店商品列表响应格式无法识别")
        total = container.get("total")
        has_total = isinstance(total, int | str) and str(total).isdigit()
        return rows, int(total) if has_total else len(rows)

    async def list_skus(self, access_token: str, product_id: str) -> list[dict[str, Any]]:
        """获取商品的 SKU 列表，对应开放平台 `sku/list`。

        改价接口 `sku/editPrice` 必须传真实 sku_id，而商品列表接口不返回该字段，
        因此按商品维度实时查询（按需调用，避免同步阶段产生不必要的付费调用）。
        """
        payload = await self.call_api("sku/list", access_token, product_id=str(product_id))
        container = payload if isinstance(payload, dict) else {}
        rows = (
            container.get("sku_list")
            or container.get("skus")
            or container.get("list")
            or []
        )
        if isinstance(rows, dict):
            rows = list(rows.values())
        if not isinstance(rows, list):
            raise DouyinApiError("抖店 SKU 列表响应格式无法识别")
        return [row for row in rows if isinstance(row, dict)]

    async def get_product_detail(self, access_token: str, product_id: str) -> dict[str, Any]:
        """查询单个商品详情，对应开放平台 `product.detail`。"""
        payload = await self.call_api("product.detail", access_token, product_id=product_id)
        if not isinstance(payload, dict):
            raise DouyinApiError("抖店商品详情响应缺少 data")
        if isinstance(payload.get("product"), dict):
            return payload["product"]
        return payload

    async def update_sku_price(
        self, access_token: str, *, product_id: str, sku_id: str, price_yuan: float
    ) -> None:
        """修改 SKU 售价，对应开放平台 `sku/editPrice`。

        平台要求 price 为整数分。测试店铺对 SKU 售价有上限约束（如 ≤ 0.1 元），
        这类限制由平台侧返回业务错误，此处如实向上抛出。
        """
        fen = int(round(float(price_yuan) * 100))
        await self.call_api(
            "sku/editPrice",
            access_token,
            product_id=str(product_id),
            sku_id=str(sku_id),
            price=fen,
        )

    async def set_offline(self, access_token: str, product_ids: list[str]) -> None:
        """商品下架，对应开放平台 `product/setOffline`。"""
        await self.call_api(
            "product/setOffline", access_token, product_ids=[str(pid) for pid in product_ids]
        )

    async def launch_product(self, access_token: str, product_id: str) -> None:
        """商品上架，对应开放平台 `product/launchProduct`。"""
        await self.call_api("product/launchProduct", access_token, product_id=str(product_id))

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
        data: dict[str, str] | None = None,
        max_attempts: int,
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
                    if method == "GET":
                        response = await client.get(url, params=params)
                    else:
                        response = await client.post(url, data=data)
                if response.status_code >= 500:
                    if attempt + 1 < attempts:
                        await asyncio.sleep(0.2 * (2**attempt))
                        continue
                    raise DouyinApiError(
                        f"抖店服务暂时不可用（HTTP {response.status_code}）", retryable=True
                    )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise DouyinApiError("抖店服务返回了非对象 JSON")
                return payload
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.2 * (2**attempt))
                    continue
            except (httpx.HTTPStatusError, ValueError) as exc:
                raise DouyinApiError("抖店服务返回了无法处理的响应") from exc
        raise DouyinApiError("连接抖店服务超时或网络不可用", retryable=True) from last_error
