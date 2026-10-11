from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class ProviderDefinition:
    id: str
    name: str
    protocol: str
    description: str
    default_base_url: str
    requires_api_key: bool
    capabilities: tuple[str, ...]
    documentation_url: str | None = None


PROVIDERS = (
    ProviderDefinition(
        id="openai",
        name="OpenAI",
        protocol="openai-compatible",
        description="OpenAI 官方 API，兼容 chat / image / embedding 能力。",
        default_base_url="https://api.openai.com/v1",
        requires_api_key=True,
        capabilities=("text", "image", "embedding"),
        documentation_url="https://platform.openai.com/docs/api-reference/models",
    ),
    ProviderDefinition(
        id="openrouter",
        name="OpenRouter",
        protocol="openai-compatible",
        description="OpenRouter 聚合网关，一个 Key 访问多家厂商模型，兼容 OpenAI 协议。",
        default_base_url="https://openrouter.ai/api/v1",
        requires_api_key=True,
        capabilities=("text", "multimodal"),
        documentation_url="https://openrouter.ai/docs/api-reference/list-available-models",
    ),
    ProviderDefinition(
        id="anthropic",
        name="Anthropic",
        protocol="anthropic",
        description="Claude 模型，使用 Anthropic 原生消息协议。",
        default_base_url="https://api.anthropic.com",
        requires_api_key=True,
        capabilities=("text", "multimodal"),
        documentation_url="https://docs.anthropic.com/en/api/models-list",
    ),
    ProviderDefinition(
        id="gemini",
        name="Google Gemini",
        protocol="gemini",
        description="Google Gemini API，支持文本和多模态模型。",
        default_base_url="https://generativelanguage.googleapis.com/v1beta",
        requires_api_key=True,
        capabilities=("text", "multimodal", "embedding"),
        documentation_url="https://ai.google.dev/gemini-api/docs/models",
    ),
    ProviderDefinition(
        id="ollama",
        name="Ollama（本地）",
        protocol="ollama",
        description="连接本机或局域网 Ollama，不需要云端 API Key。",
        default_base_url="http://127.0.0.1:11434",
        requires_api_key=False,
        capabilities=("text", "multimodal", "embedding"),
        documentation_url="https://docs.ollama.com/api/tags",
    ),
    ProviderDefinition(
        id="custom-openai",
        name="自定义 OpenAI 兼容厂商",
        protocol="openai-compatible",
        description="适用于 DeepSeek、通义千问、Moonshot 等兼容 OpenAI 协议的服务。",
        default_base_url="https://api.example.com/v1",
        requires_api_key=True,
        capabilities=("text", "multimodal"),
    ),
    ProviderDefinition(
        id="mock",
        name="演示模型（无需 Key）",
        protocol="mock",
        description="本地演示模型，明确标记为 Demo，不会调用外部服务。",
        default_base_url="http://demo.local",
        requires_api_key=False,
        capabilities=("text", "image", "video_script"),
    ),
)
PROVIDER_BY_ID = {item.id: item for item in PROVIDERS}

# OpenRouter 可选归因头，用于在 OpenRouter 控制台区分来源应用；不含任何凭据。
# 值必须保持 ASCII：HTTP 头按 latin-1 编码发送，非 ASCII 会触发 UnicodeEncodeError。
OPENROUTER_APP_REFERER = "http://127.0.0.1:5173"
OPENROUTER_APP_TITLE = "Ops Command Center"


def get_provider(provider_id: str) -> ProviderDefinition:
    try:
        return PROVIDER_BY_ID[provider_id]
    except KeyError as exc:
        raise ValueError(f"不支持的 AI 厂商：{provider_id}") from exc


def auth_headers(provider: ProviderDefinition, api_key: str | None) -> dict[str, str]:
    """Build request headers for OpenAI-compatible providers.

    OpenRouter additionally attributes traffic with X-Title; no credential is echoed.
    HTTP headers are encoded as latin-1 by httpx, so non-ASCII values are dropped
    instead of raising UnicodeEncodeError at send time.
    """
    headers = {"Authorization": f"Bearer {api_key or ''}"}
    if provider.id == "openrouter":
        for name, value in (
            ("HTTP-Referer", OPENROUTER_APP_REFERER),
            ("X-Title", OPENROUTER_APP_TITLE),
        ):
            try:
                value.encode("ascii")
            except UnicodeEncodeError:
                continue
            headers[name] = value
    return headers


def mask_secret(secret: str | None) -> str | None:
    if not secret:
        return None
    if len(secret) <= 8:
        return "*" * len(secret)
    return f"{secret[:3]}{'*' * max(4, len(secret) - 7)}{secret[-4:]}"


def provider_error_detail(response: httpx.Response, action: str) -> str:
    """Build a safe error message, surfacing vendor messages on auth/rate-limit errors.

    The vendor body is only echoed when it parses to a short error string and does
    not look like a credential, so a bad Key never leaks back into the response.
    """
    detail = f"{action}失败（HTTP {response.status_code}）"
    if response.status_code not in (401, 403, 429):
        return detail
    try:
        payload = response.json()
    except ValueError:
        return detail
    if not isinstance(payload, dict):
        return detail
    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message")
    elif isinstance(error, str):
        message = error
    else:
        message = None
    if not isinstance(message, str) or not message.strip():
        return detail
    cleaned = " ".join(message.split())[:120]
    if "sk-" in cleaned.lower():
        return detail
    return f"{detail}：{cleaned}"


def _ensure_success(response: httpx.Response, action: str) -> None:
    if response.is_error:
        # Do not include response text or URL: Gemini carries the API key in query params.
        raise ValueError(provider_error_detail(response, action))

def _capabilities(model_id: str, provider: ProviderDefinition) -> list[str]:
    lowered = model_id.lower()
    capabilities = set(provider.capabilities)
    if any(word in lowered for word in ("embed", "bge", "text-embedding")):
        capabilities = {"embedding"}
    elif any(word in lowered for word in ("vision", "vl", "4o", "sonnet", "gemini")):
        capabilities.add("multimodal")
    if any(word in lowered for word in ("image", "dall-e", "flux")):
        capabilities = {"image"}
    return sorted(capabilities)


def _zero_price(value: Any) -> bool:
    try:
        return float(value) == 0.0
    except (TypeError, ValueError):
        return False


def _is_free(row: dict[str, Any], model_id: str) -> bool | None:
    """Infer whether a model is free from provider pricing metadata.

    Returns None when the provider exposes no pricing, so the UI can fall back to
    showing every model instead of hiding all of them.
    """
    pricing = row.get("pricing")
    if isinstance(pricing, dict):
        keys = ("prompt", "completion")
        if all(key in pricing for key in keys):
            return all(_zero_price(pricing.get(key)) for key in keys)
    if model_id.endswith(":free"):
        return True
    return None


def _sorted_models(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Free models first, then unknown pricing, then paid, each by model id."""
    return sorted(
        models,
        key=lambda item: (item.get("is_free") is not True, str(item.get("model_id", ""))),
    )


def _mock_models(provider: ProviderDefinition) -> list[dict[str, Any]]:
    if provider.id == "mock":
        values = [
            ("demo-copy-v1", "运营文案演示模型", ["text"]),
            ("demo-visual-v1", "主图创意演示模型", ["image"]),
            ("demo-script-v1", "短视频脚本演示模型", ["video_script", "text"]),
        ]
    elif provider.protocol == "openai-compatible":
        values = [("manual-model", "手动填写模型（连接后可刷新）", list(provider.capabilities))]
    else:
        values = [
            (f"{provider.id}-manual", "手动填写模型（连接后可刷新）", list(provider.capabilities))
        ]
    return [
        {"model_id": model_id, "display_name": name, "capabilities": caps, "is_free": True}
        for model_id, name, caps in values
    ]


async def discover_models(
    provider: ProviderDefinition, base_url: str, api_key: str | None
) -> list[dict[str, Any]]:
    """Fetch model metadata through a provider-specific adapter.

    The adapter returns normalized model rows and deliberately never includes credentials.
    """
    if provider.protocol == "mock":
        return _mock_models(provider)
    if provider.requires_api_key and not api_key:
        raise ValueError("该厂商需要 API Key，请先填写后再测试连接")

    # 模型列表响应可能上兆（OpenRouter 有数百个模型），连接和读取都要留足余量。
    timeout = httpx.Timeout(30.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        if provider.protocol == "openai-compatible":
            response = await client.get(
                f"{base_url.rstrip('/')}/models",
                headers=auth_headers(provider, api_key),
            )
            _ensure_success(response, "模型发现")
            payload = response.json()
            rows = payload.get("data", []) if isinstance(payload, dict) else []
            return _sorted_models(
                [
                    {
                        "model_id": str(row.get("id")),
                        "display_name": str(row.get("name") or row.get("id")),
                        "capabilities": _capabilities(str(row.get("id")), provider),
                        "is_free": _is_free(row, str(row.get("id"))),
                    }
                    for row in rows
                    if isinstance(row, dict) and row.get("id")
                ]
            )
        if provider.protocol == "anthropic":
            response = await client.get(
                f"{base_url.rstrip('/')}/v1/models",
                headers={"x-api-key": api_key or "", "anthropic-version": "2023-06-01"},
            )
            _ensure_success(response, "模型发现")
            payload = response.json()
            rows = payload.get("data", []) if isinstance(payload, dict) else []
            return _sorted_models(
                [
                    {
                        "model_id": str(row.get("id")),
                        "display_name": str(row.get("display_name") or row.get("id")),
                        "capabilities": _capabilities(str(row.get("id")), provider),
                        "is_free": None,
                    }
                    for row in rows
                    if isinstance(row, dict) and row.get("id")
                ]
            )
        if provider.protocol == "gemini":
            response = await client.get(
                f"{base_url.rstrip('/')}/models",
                params={"key": api_key},
            )
            _ensure_success(response, "模型发现")
            payload = response.json()
            rows = payload.get("models", []) if isinstance(payload, dict) else []
            return _sorted_models(
                [
                    {
                        "model_id": str(row.get("name", "")).removeprefix("models/"),
                        "display_name": str(row.get("displayName") or row.get("name")),
                        "capabilities": _capabilities(str(row.get("name")), provider),
                        "is_free": None,
                    }
                    for row in rows
                    if isinstance(row, dict) and row.get("name")
                ]
            )
        if provider.protocol == "ollama":
            response = await client.get(f"{base_url.rstrip('/')}/api/tags")
            _ensure_success(response, "模型发现")
            payload = response.json()
            rows = payload.get("models", []) if isinstance(payload, dict) else []
            return _sorted_models(
                [
                    {
                        "model_id": str(row.get("name")),
                        "display_name": str(row.get("name")),
                        "capabilities": _capabilities(str(row.get("name")), provider),
                        "is_free": True,
                    }
                    for row in rows
                    if isinstance(row, dict) and row.get("name")
                ]
            )
    raise ValueError("该厂商暂未配置模型发现适配器")


