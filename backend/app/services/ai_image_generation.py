"""真实图片生成适配器。

当前只实现 OpenAI 兼容协议的图片接口（`POST {base}/images/generations`），
它覆盖 OpenAI 官方以及大量以 OpenAI 兼容协议暴露图片能力的中转/云厂商。
其他协议（Anthropic 无图片生成、Gemini/Ollama 图片接口形态不同）如实报错，
不伪造、不降级冒充。

与文本生成同一条安全线：真实调用由 `AI_LIVE_GENERATION_ENABLED` 控制，
默认关闭；API Key 只从服务端加密配置读取，不进日志与响应。
"""
from __future__ import annotations

import base64
import binascii

import httpx

from app.services.ai_generation import AiGenerationError, _ensure_success
from app.services.ai_provider_registry import ProviderDefinition, auth_headers


async def generate_image(
    provider: ProviderDefinition,
    base_url: str,
    api_key: str | None,
    model_id: str,
    prompt: str,
    size: str = "1024x1024",
) -> bytes:
    """生成一张图片并返回字节内容。"""
    if provider.requires_api_key and not api_key:
        raise AiGenerationError("该 AI 配置未保存 API Key")
    if provider.protocol != "openai-compatible":
        raise AiGenerationError(
            "该厂商暂未配置图片生成适配器（当前支持 OpenAI 兼容协议的图片接口）"
        )

    timeout = httpx.Timeout(180.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.post(
            f"{base_url.rstrip('/')}/images/generations",
            headers=auth_headers(provider, api_key),
            json={
                "model": model_id,
                "prompt": prompt,
                "size": size,
                "n": 1,
                "response_format": "b64_json",
            },
        )
        _ensure_success(response, "图片生成")
        payload = response.json()
        data = payload.get("data", []) if isinstance(payload, dict) else []
        if not data or not isinstance(data[0], dict):
            raise AiGenerationError("图片接口未返回结果")

        item = data[0]
        encoded = item.get("b64_json")
        if isinstance(encoded, str) and encoded:
            try:
                return base64.b64decode(encoded)
            except (binascii.Error, ValueError) as exc:
                raise AiGenerationError("图片接口返回的 base64 数据无法解析") from exc

        url = item.get("url")
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            download = await client.get(url)
            if download.is_error:
                raise AiGenerationError(f"图片 URL 下载失败（HTTP {download.status_code}）")
            return download.content

        raise AiGenerationError("图片接口未返回 b64_json 或 url 字段")
