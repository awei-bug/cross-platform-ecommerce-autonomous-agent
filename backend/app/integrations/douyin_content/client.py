"""抖音开放平台内容投稿（open.douyin.com，「投稿到抖音」能力）。

与抖店电商 API（openapi-fxg.jinritemai.com）不同，这里是面向 C 端的用户授权：
开放应用用 client_key/client_secret 换取用户 access_token，再调用
`/api/douyin/v1/video/create_video/` 上传视频二进制，代替用户发布短视频内容。

抖音开放平台「投稿到抖音」对个人开放申请（普通用户可注册开放应用，审核制，
需真实应用载体），因此本项目把它作为"个人可达的官方内容发布通道"——区别于
小红书（不对普通开发者开放笔记发布 API）与微信（个人订阅号无发布权限）。

所有网络调用均通过 httpx 注入 transport，契约测试用 MockTransport 覆盖同代码路径，
无需真实凭证或应用即可验证协议正确性。
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx


class DouyinContentApiError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str | int | None = None,
        sub_code: str | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.sub_code = sub_code
        self.retryable = retryable


@dataclass(frozen=True)
class DouyinContentToken:
    access_token: str
    refresh_token: str | None
    open_id: str | None
    access_token_expires_at: datetime | None
    refresh_token_expires_at: datetime | None
    scopes: list[str]


CONTENT_DEFAULT_SCOPES = ["video.create", "renew_refresh_token"]


def _seconds_to_expiry(now: datetime, seconds: int | None) -> datetime | None:
    return now + timedelta(seconds=seconds) if seconds is not None else None


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise DouyinContentApiError("抖音内容 Token 响应中的有效期不是有效整数") from exc


class DouyinContentClient:
    def __init__(
        self,
        *,
        client_key: str,
        client_secret: str,
        redirect_uri: str,
        api_base_url: str = "https://open.douyin.com",
        timeout_seconds: float = 15.0,
        max_attempts: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.client_key = client_key
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.api_base_url = api_base_url.rstrip("/")
        self.timeout = httpx.Timeout(timeout_seconds)
        self.max_attempts = max(1, max_attempts)
        self.transport = transport

    @property
    def auth_base_url(self) -> str:
        return f"{self.api_base_url}/platform/oauth/connect"

    def build_authorization_url(
        self, state: str, scopes: list[str] | None = None
    ) -> str:
        query = urlencode(
            {
                "client_key": self.client_key,
                "response_type": "code",
                "scope": ",".join(scopes or CONTENT_DEFAULT_SCOPES),
                "redirect_uri": self.redirect_uri,
                "state": state,
            }
        )
        return f"{self.auth_base_url}/?{query}"

    async def exchange_code(self, code: str) -> DouyinContentToken:
        """用授权 code 换取用户 access_token（含 refresh_token 与 open_id）。"""
        data = {
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
        }
        payload = await self._request(
            "POST", f"{self.api_base_url}/oauth/access_token/", data=data, max_attempts=1
        )
        return self._parse_token(payload)

    def _parse_token(self, payload: dict[str, Any]) -> DouyinContentToken:
        # 抖音开放平台 token 接口成功时直接在顶层返回字段，失败时返回 status_code。
        status_code = payload.get("status_code")
        if status_code is not None and status_code != 0:
            raise DouyinContentApiError(
                str(payload.get("detail") or "抖音内容授权失败"),
                code=status_code,
                retryable=False,
            )
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise DouyinContentApiError("抖音内容授权响应缺少 access_token")
        now = datetime.now(UTC)
        return DouyinContentToken(
            access_token=access_token,
            refresh_token=payload.get("refresh_token"),
            open_id=payload.get("open_id"),
            access_token_expires_at=_seconds_to_expiry(
                now, _coerce_int(payload.get("expires_in"))
            ),
            refresh_token_expires_at=_seconds_to_expiry(
                now, _coerce_int(payload.get("refresh_expires_in"))
            ),
            scopes=str(payload.get("scope") or "").split(",") if payload.get("scope") else [],
        )

    async def create_video(
        self,
        access_token: str,
        *,
        title: str,
        text: str,
        video: bytes,
        filename: str = "video.mp4",
        cover_url: str | None = None,
    ) -> dict[str, Any]:
        """投稿到抖音：上传视频二进制并发布。

        真实接口为 multipart/form-data，包含 `video`（二进制）与 `body`
        （JSON 字符串，含文案 text 等）。成功返回 item_id / video_id。
        """
        body_json = {
            "text": (text or title).strip(),
            "app_name": "运营中枢",
            "poi_id": "",
            "micro_app_id": "",
        }
        if cover_url:
            body_json["cover_url"] = cover_url
        form = {"body": json.dumps(body_json, ensure_ascii=False)}
        files = {"video": (filename, video, "video/mp4")}
        payload = await self._request(
            "POST",
            f"{self.api_base_url}/api/douyin/v1/video/create_video/",
            data=form,
            files=files,
            max_attempts=self.max_attempts,
        )
        error_code = payload.get("error_code")
        if error_code is not None and error_code != 0:
            data_detail = (payload.get("data") or {}).get("description")
            detail = payload.get("detail") or data_detail or "投稿失败"
            raise DouyinContentApiError(str(detail), code=error_code, retryable=False)
        data = payload.get("data") or {}
        data_error = data.get("error_code")
        if data_error is not None and data_error != 0:
            raise DouyinContentApiError(
                str(data.get("description") or "投稿失败"), code=data_error, retryable=False
            )
        item_id = data.get("item_id") or data.get("video_id")
        if not item_id:
            raise DouyinContentApiError("抖音内容投稿响应缺少 item_id", retryable=False)
        return {
            "item_id": str(item_id),
            "video_id": str(data.get("video_id") or item_id),
            "share_id": data.get("share_id"),
        }

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
        data: dict[str, str] | None = None,
        files: dict[str, Any] | None = None,
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
                    response = await client.request(
                        method, url, params=params, data=data, files=files
                    )
                if response.status_code >= 500:
                    if attempt + 1 < attempts:
                        await asyncio.sleep(0.2 * (2**attempt))
                        continue
                    raise DouyinContentApiError(
                        f"抖音内容服务暂时不可用（HTTP {response.status_code}）", retryable=True
                    )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise DouyinContentApiError("抖音内容服务返回了非对象 JSON")
                return payload
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.2 * (2**attempt))
                    continue
            except (httpx.HTTPStatusError, ValueError) as exc:
                raise DouyinContentApiError("抖音内容服务返回了无法处理的响应") from exc
        raise DouyinContentApiError(
            "连接抖音内容服务超时或网络不可用", retryable=True
        ) from last_error
