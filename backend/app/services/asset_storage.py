from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote, urlparse

import httpx

from app.core.config import get_settings


class AssetStorageError(RuntimeError):
    """Raised when an asset cannot be stored or read."""


@dataclass(frozen=True)
class StoredAsset:
    object_key: str
    content_type: str
    file_size: int


class MinioHttpClient:
    """Small S3-compatible client using MinIO's AWS Signature V4 API.

    Keeping this adapter on top of httpx avoids making the API process depend on a
    second SDK and lets the same code work with the Docker MinIO service or S3.
    """

    def __init__(self) -> None:
        settings = get_settings()
        parsed = urlparse(settings.minio_endpoint)
        if not parsed.hostname:
            raise AssetStorageError("MINIO_ENDPOINT 无效")
        self.endpoint = settings.minio_endpoint.rstrip("/")
        self.host = parsed.hostname + (f":{parsed.port}" if parsed.port else "")
        self.access_key = settings.minio_access_key
        self.secret_key = settings.minio_secret_key
        self.region = settings.minio_region
        self.bucket = settings.minio_bucket

    @staticmethod
    def _sign(key: bytes, value: str) -> bytes:
        return hmac.new(key, value.encode("utf-8"), hashlib.sha256).digest()

    def _signature(
        self, method: str, path: str, headers: dict[str, str], body: bytes
    ) -> dict[str, str]:
        now = datetime.now(UTC)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        short_date = now.strftime("%Y%m%d")
        payload_hash = hashlib.sha256(body).hexdigest()
        signed = {key.lower(): value.strip() for key, value in headers.items()}
        signed["host"] = self.host
        signed["x-amz-content-sha256"] = payload_hash
        signed["x-amz-date"] = amz_date
        canonical_headers = "".join(f"{key}:{signed[key]}\n" for key in sorted(signed))
        signed_headers = ";".join(sorted(signed))
        canonical_request = "\n".join(
            [method, path, "", canonical_headers, signed_headers, payload_hash]
        )
        scope = f"{short_date}/{self.region}/s3/aws4_request"
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                scope,
                hashlib.sha256(canonical_request.encode()).hexdigest(),
            ]
        )
        date_key = self._sign(("AWS4" + self.secret_key).encode(), short_date)
        region_key = self._sign(date_key, self.region)
        service_key = self._sign(region_key, "s3")
        signing_key = self._sign(service_key, "aws4_request")
        signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
        return {
            **headers,
            "Host": self.host,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
            "Authorization": (
                f"AWS4-HMAC-SHA256 Credential={self.access_key}/{scope}, "
                f"SignedHeaders={signed_headers}, Signature={signature}"
            ),
        }

    def _object_path(self, object_key: str = "") -> str:
        bucket = quote(self.bucket, safe="-_.~")
        suffix = "/".join(quote(part, safe="-_.~") for part in object_key.split("/") if part)
        return f"/{bucket}/{suffix}" if suffix else f"/{bucket}"

    def request(
        self,
        method: str,
        object_key: str = "",
        body: bytes = b"",
        content_type: str | None = None,
    ):
        path = self._object_path(object_key)
        headers = {"Content-Type": content_type} if content_type else {}
        signed_headers = self._signature(method, path, headers, body)
        try:
            response = httpx.request(
                method,
                f"{self.endpoint}{path}",
                headers=signed_headers,
                content=body,
                timeout=httpx.Timeout(20.0, connect=5.0),
            )
        except httpx.HTTPError as exc:
            raise AssetStorageError("MinIO 网络请求失败，请检查服务状态") from exc
        return response


def _backend() -> str:
    value = get_settings().asset_storage_backend.strip().lower()
    if value not in {"local", "minio"}:
        raise AssetStorageError("ASSET_STORAGE_BACKEND 仅支持 local 或 minio")
    return value


def _local_path(object_key: str) -> Path:
    root = Path(get_settings().asset_storage_local_path).resolve()
    target = (root / object_key).resolve()
    if root != target and root not in target.parents:
        raise AssetStorageError("素材对象路径无效")
    return target


def _ensure_success(response: httpx.Response, action: str) -> None:
    if response.is_error:
        raise AssetStorageError(f"{action}失败（HTTP {response.status_code}）")


def _ensure_bucket(client: MinioHttpClient) -> None:
    response = client.request("HEAD")
    if response.status_code == 404:
        _ensure_success(client.request("PUT"), "创建 MinIO 存储桶")
    elif response.is_error:
        _ensure_success(response, "检查 MinIO 存储桶")


def put_bytes(object_key: str, content: bytes, content_type: str) -> StoredAsset:
    if not content:
        raise AssetStorageError("素材文件不能为空")
    if _backend() == "local":
        path = _local_path(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    else:
        client = MinioHttpClient()
        _ensure_bucket(client)
        _ensure_success(client.request("PUT", object_key, content, content_type), "上传素材")
    return StoredAsset(object_key, content_type, len(content))


def get_bytes(object_key: str) -> tuple[bytes, str]:
    if _backend() == "local":
        path = _local_path(object_key)
        if not path.is_file():
            raise AssetStorageError("素材文件不存在")
        return path.read_bytes(), "application/octet-stream"

    response = MinioHttpClient().request("GET", object_key)
    _ensure_success(response, "读取素材")
    return response.content, response.headers.get("Content-Type", "application/octet-stream")


def delete_object(object_key: str) -> None:
    if _backend() == "local":
        path = _local_path(object_key)
        if path.is_file():
            path.unlink()
        return
    _ensure_success(MinioHttpClient().request("DELETE", object_key), "清理素材")

