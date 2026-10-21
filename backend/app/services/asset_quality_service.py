"""素材平台质检：尺寸、敏感词与版权检查。

三条检查的真实程度是分层的，文档与界面都如实标注：

- **平台尺寸**：真实检查。图片版本用 Pillow 读取宽高，对照内置的多平台主图
  规则表（规则集中在本模块 `PLATFORM_IMAGE_RULES`，可扩展）；非图片或
  无文件版本跳过；
- **敏感词**：真实检查。内置广告法极限词/违禁词词库（`SENSITIVE_WORDS`），
  扫描素材标题与文本内容，命中即列明词与位置来源；
- **版权**：当前为占位（`skipped`），真实版权库接入前不做结论，不假装通过。

质检结果写入 `asset_quality_checks` 记录，并聚合更新版本
`quality_status` 与 `quality_issues`。质检不阻断人工确认流程，
只做风险提示（与项目"人工确认"主线一致）。
"""
from __future__ import annotations

import io
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.db.models import AssetModel, AssetQualityCheckModel, AssetVersionModel

SHANGHAI = ZoneInfo("Asia/Shanghai")

# 平台主图规则（演示环境内置规则，来自各平台公开的商家规范摘要；
# 平台规则会调整，以官方最新文档为准，规则表可扩展）
PLATFORM_IMAGE_RULES: dict[str, dict] = {
    "taobao": {
        "label": "淘宝",
        "min_width": 800,
        "min_height": 800,
        "square": True,
        "note": "主图建议 800x800 以上正方形，支持放大镜",
    },
    "douyin": {
        "label": "抖店",
        "min_width": 600,
        "min_height": 600,
        "square": True,
        "note": "主图 1:1，建议 600x600 以上",
    },
    "pinduoduo": {
        "label": "拼多多",
        "min_width": 480,
        "min_height": 480,
        "square": False,
        "note": "主图建议 480x480 以上",
    },
}

# 广告法极限词与电商违禁词（演示词库，真实生产需接入完整词库与人工复核）
SENSITIVE_WORDS: tuple[str, ...] = (
    "国家级",
    "世界级",
    "最高级",
    "史上最",
    "全网最低",
    "全网最",
    "第一品牌",
    "销量第一",
    "全国第一",
    "顶级",
    "极致",
    "绝对",
    "唯一",
    "首个",
    "独家",
    "冠军",
    "王牌",
    "领先品牌",
    "100%",
    "纯天然",
    "无副作用",
    "包治",
    "根治",
    "特效",
    "祖传",
    "秘方",
    "免检",
    "特供",
    "专供",
    "刷单",
    "好评返现",
)


def _version_label(version: AssetVersionModel) -> str:
    return f"版本 v{version.version_number}"


def check_platform_size(version: AssetVersionModel, content: bytes) -> dict:
    """真实读取图片尺寸并对照平台规则。返回单条检查结果。"""
    if not version.object_key:
        return {
            "check_type": "platform_size",
            "status": "skipped",
            "message": "该版本没有文件，跳过尺寸检查",
        }
    content_type = version.content_type or ""
    if not content_type.startswith("image/"):
        return {
            "check_type": "platform_size",
            "status": "skipped",
            "message": "非图片素材，跳过尺寸检查（视频规格检查待接入）",
        }
    try:
        from PIL import Image

        with Image.open(io.BytesIO(content)) as image:
            width, height = image.size
    except Exception:
        return {
            "check_type": "platform_size",
            "status": "warning",
            "message": "图片尺寸无法解析，请确认文件未损坏",
        }

    issues: list[str] = []
    for rule in PLATFORM_IMAGE_RULES.values():
        if width < rule["min_width"] or height < rule["min_height"]:
            issues.append(
                f"{rule['label']}：{width}x{height} 低于 {rule['min_width']}x{rule['min_height']}"
            )
            continue
        if rule["square"] and width != height:
            issues.append(f"{rule['label']}：主图需 1:1 正方形，当前 {width}x{height}")
    if issues:
        return {
            "check_type": "platform_size",
            "status": "warning",
            "message": f"图片 {width}x{height}，" + "；".join(issues),
        }
    return {
        "check_type": "platform_size",
        "status": "passed",
        "message": f"图片 {width}x{height}，满足内置平台主图规则（"
        + "、".join(rule["label"] for rule in PLATFORM_IMAGE_RULES.values())
        + "）",
    }


def check_sensitive_words(asset_title: str, version_content: str) -> dict:
    """真实扫描内置违禁词库，命中即列明。

    按词长降序匹配并移除已命中片段，避免包含关系的词重复上报
    （例如「全网最低」命中后不再单独报「全网最」）。
    """
    remaining = f"{asset_title}\n{version_content}"
    hits: list[str] = []
    for word in sorted(SENSITIVE_WORDS, key=len, reverse=True):
        if word in remaining:
            hits.append(word)
            remaining = remaining.replace(word, "")
    if hits:
        return {
            "check_type": "sensitive_words",
            "status": "warning",
            "message": "命中违禁/极限词：" + "、".join(hits) + "（建议人工复核上下文）",
        }
    return {
        "check_type": "sensitive_words",
        "status": "passed",
        "message": f"未命中内置词库（{len(SENSITIVE_WORDS)} 个词）",
    }


def check_copyright(version: AssetVersionModel) -> dict:
    """版权检查占位：接入真实版权库前不做结论。"""
    return {
        "check_type": "copyright",
        "status": "skipped",
        "message": "版权检查待接入版权库，当前不做结论（不冒充通过）",
    }


def _aggregate_status(results: list[dict]) -> tuple[str, list[str]]:
    issues = [
        f"{item['check_type']}：{item['message']}"
        for item in results
        if item["status"] in {"warning", "failed"}
    ]
    if any(item["status"] == "failed" for item in results):
        return "failed", issues
    if any(item["status"] == "warning" for item in results):
        return "warning", issues
    return "passed", issues


def run_quality_checks(
    db: Session, version: AssetVersionModel, *, content: bytes | None = None
) -> dict:
    """对指定版本执行全部质检并落库。

    content 未提供时（例如生成任务刚创建版本、没有再读一次对象存储），
    涉及文件的尺寸检查自动跳过，其余检查照常执行。
    """
    asset = db.get(AssetModel, version.asset_id)
    title = asset.title if asset else ""
    if content is None and version.object_key:
        try:
            from app.services.asset_storage import get_bytes

            content, _ = get_bytes(version.object_key)
        except Exception:
            content = None

    results = []
    if content is not None:
        results.append(check_platform_size(version, content))
    elif version.object_key:
        results.append(
            {
                "check_type": "platform_size",
                "status": "skipped",
                "message": "文件不可读取，尺寸检查跳过",
            }
        )
    else:
        results.append(
            {
                "check_type": "platform_size",
                "status": "skipped",
                "message": "该版本没有文件，跳过尺寸检查",
            }
        )
    results.append(check_sensitive_words(title, version.content))
    results.append(check_copyright(version))

    timestamp = datetime.now(SHANGHAI)
    for item in results:
        db.add(
            AssetQualityCheckModel(
                id=f"asset-check-{uuid4().hex[:12]}",
                version_id=version.id,
                check_type=item["check_type"],
                status=item["status"],
                message=item["message"][:500],
                created_at=timestamp,
            )
        )
    status, issues = _aggregate_status(results)
    version.quality_status = status
    version.quality_issues = issues
    db.commit()
    return {"quality_status": status, "quality_issues": issues, "checks": results}
