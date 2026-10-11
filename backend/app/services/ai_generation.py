from __future__ import annotations

from typing import Any

import httpx

from app.services.ai_provider_registry import (
    ProviderDefinition,
    auth_headers,
    provider_error_detail,
)


class AiGenerationError(ValueError):
    """A safe, user-facing error raised when a provider cannot generate text."""


def _ensure_success(response: httpx.Response, action: str) -> None:
    if response.is_error:
        # Never include response text or the request URL: Gemini puts the API key in
        # the query string and provider bodies may echo sensitive request details.
        raise AiGenerationError(provider_error_detail(response, action))


def _content_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        chunks = []
        for item in value:
            if isinstance(item, str):
                chunks.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                chunks.append(item["text"])
        return "".join(chunks).strip()
    return ""


def _reasoning_fallback(message: Any) -> str:
    """Reasoning models may put all output in reasoning fields with empty content."""
    if not isinstance(message, dict):
        return ""
    for key in ("reasoning_content", "reasoning", "reasoning_details"):
        value = message.get(key)
        text = _content_text(value)
        if text:
            return text
    return ""


def _require_text(content: str) -> str:
    if not content:
        raise AiGenerationError("模型返回了空内容，请检查模型能力或提示词")
    return content


def _openai_messages(prompt: str, asset_type: str) -> list[dict[str, str]]:
    kind = {"copy": "商品运营文案", "video_script": "短视频脚本", "template": "商品素材模板"}.get(
        asset_type, "电商素材"
    )
    return [
        {
            "role": "system",
            "content": (
                f"你是电商运营素材助手，负责生成{kind}。只输出候选内容，不要声称已发布或已通过平台审核。"
                "避免夸大功效、绝对化承诺和无法验证的事实。"
            ),
        },
        {"role": "user", "content": prompt},
    ]


async def generate_text(
    provider: ProviderDefinition,
    base_url: str,
    api_key: str | None,
    model_id: str,
    prompt: str,
    asset_type: str,
    max_tokens: int | None = None,
) -> str:
    """Generate text through a normalized provider adapter.

    This is intentionally limited to copy/script/template outputs. Image/video file
    generation needs an object-storage and media pipeline and is not faked here.
    """
    if asset_type not in {"copy", "video_script", "template"}:
        raise AiGenerationError("当前阶段仅支持真实文案、脚本和模板生成，图片文件生成尚未接入")
    if provider.requires_api_key and not api_key:
        raise AiGenerationError("该 AI 配置未保存 API Key")

    timeout = httpx.Timeout(90.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        if provider.protocol == "openai-compatible":
            response = await client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers=auth_headers(provider, api_key),
                json={
                    "model": model_id,
                    "messages": _openai_messages(prompt, asset_type),
                    "temperature": 0.7,
                    **({"max_tokens": max_tokens} if max_tokens else {}),
                },
            )
            _ensure_success(response, "模型生成")
            payload = response.json()
            choices = payload.get("choices", []) if isinstance(payload, dict) else []
            message = (
                choices[0].get("message", {})
                if choices and isinstance(choices[0], dict)
                else {}
            )
            content = _content_text(message.get("content")) or _reasoning_fallback(message)
            return _require_text(content)

        if provider.protocol == "anthropic":
            response = await client.post(
                f"{base_url.rstrip('/')}/v1/messages",
                headers={
                    "x-api-key": api_key or "",
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model_id,
                    "max_tokens": max_tokens or 2048,
                    "temperature": 0.7,
                    "system": "你是电商运营素材助手，只输出候选内容，不自动发布或修改线上素材。",
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            _ensure_success(response, "模型生成")
            payload = response.json()
            content = payload.get("content", []) if isinstance(payload, dict) else []
            return _require_text(_content_text(content))

        if provider.protocol == "gemini":
            response = await client.post(
                f"{base_url.rstrip('/')}/models/{model_id}:generateContent",
                params={"key": api_key},
                json={
                    "systemInstruction": {
                        "parts": [
                            {
                                "text": (
                                    "你是电商运营素材助手，只输出候选内容，不自动发布或修改线上素材。"
                                )
                            }
                        ]
                    },
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.7,
                        **({"maxOutputTokens": max_tokens} if max_tokens else {}),
                    },
                },
            )
            _ensure_success(response, "模型生成")
            payload = response.json()
            candidates = payload.get("candidates", []) if isinstance(payload, dict) else []
            content = candidates[0].get("content", {}) if candidates else {}
            return _require_text(_content_text(content.get("parts", [])))

        if provider.protocol == "ollama":
            response = await client.post(
                f"{base_url.rstrip('/')}/api/chat",
                json={
                    "model": model_id,
                    "stream": False,
                    "messages": _openai_messages(prompt, asset_type),
                    **({"options": {"num_predict": max_tokens}} if max_tokens else {}),
                },
            )
            _ensure_success(response, "模型生成")
            payload = response.json()
        message = payload.get("message", {}) if isinstance(payload, dict) else {}
        content = _content_text(message.get("content")) or _reasoning_fallback(message)
        return _require_text(content)

    raise AiGenerationError("该厂商暂未配置文本生成适配器")
