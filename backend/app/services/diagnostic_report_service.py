"""诊断报告：模板生成 + 真实模型生成，快照落库可复现。

两条生成路径的边界：

- **template**：规则模板，只做数据编排与格式化，永远可用，零外部依赖；
- **ai**：用户在「AI 模型配置」保存了可用配置且 `AI_LIVE_GENERATION_ENABLED=true`
  时才走真实模型，prompt 强制要求"只引用提供的数据点、区分事实/推测/建议"，
  模型失败时自动降级为模板并在报告中如实说明，不把失败伪装成成功。

无论哪条路径，生成时的健康分与问题清单都以 snapshot 形式落库，
报告与数据严格对应，支持复现与审计。
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import AiConfigurationModel, DiagnosticReportModel
from app.services.ai_generation import AiGenerationError, generate_text
from app.services.ai_provider_registry import get_provider
from app.services.ai_repository import api_key_for
from app.services.diagnostics_service import get_overview

SHANGHAI = ZoneInfo("Asia/Shanghai")
DEFAULT_ORG = "org-demo-001"
MAX_ISSUES_IN_PROMPT = 10


def _resolve_ai_config(db: Session, organization_id: str) -> AiConfigurationModel | None:
    """取第一个启用且已选模型的配置。"""
    rows = db.scalars(
        select(AiConfigurationModel).where(
            AiConfigurationModel.organization_id == organization_id,
            AiConfigurationModel.is_enabled.is_(True),
            AiConfigurationModel.selected_model.is_not(None),
        )
    ).all()
    return rows[0] if rows else None


def _fmt_money(value: float) -> str:
    return f"¥{value:,.2f}"


def _issue_block(issue: dict, index: int) -> str:
    lines = [
        f"### {index}. {issue['title']}",
        f"- 严重度：{issue['severity']}｜置信度：{issue['confidence']}"
        f"｜风险级别：{issue['risk_level']}｜紧迫度：{issue['urgency']}/100",
        f"- 事实：{issue['detail']}",
    ]
    for evidence in issue["evidence"]:
        lines.append(
            f"  - 指标 {evidence['metric']} = {evidence['value']}"
            f"（阈值/参考 {evidence['threshold']}，来源 {evidence['source']}）"
        )
    lines.append(f"- 预计损失：{_fmt_money(issue['estimated_loss'])}（口径：{issue['loss_note']}）")
    lines.append(f"- 建议：{issue['recommendation']}")
    return "\n".join(lines)


def render_template_report(overview: dict) -> str:
    """规则模板报告：全部内容来自 overview 数据，无任何外部生成。"""
    health = overview["health"]
    issues = overview["issues"]
    comparison = overview["comparison"]
    scope = overview["shop_id"]
    lines = [
        f"# 经营诊断报告（范围：{scope}）",
        "",
        f"- 生成时间：{overview['generated_at'].strftime('%Y-%m-%d %H:%M')}",
        f"- 数据源：{'演示种子数据' if overview['is_demo'] else '实时授权店铺'}",
        f"- 健康分算法版本：{health['algorithm_version']}",
        "- 报告类型：规则模板生成（未调用外部模型）",
        "",
        "## 一、健康分总览",
        "",
        f"**综合健康分 {health['score']} 分**（五项可解释分项加权平均）",
        "",
        "| 分项 | 得分 | 权重 | 说明 |",
        "| --- | --- | --- | --- |",
    ]
    for component in health["components"]:
        lines.append(
            f"| {component['label']} | {component['score']} | "
            f"{component['weight']:.0%} | {component['detail']} |"
        )
    lines.extend(["", "## 二、重点问题（按预计损失 x 紧迫度 x 置信度排序）", ""])
    if issues:
        for index, issue in enumerate(issues[:MAX_ISSUES_IN_PROMPT], start=1):
            lines.append(_issue_block(issue, index))
            lines.append("")
        if len(issues) > MAX_ISSUES_IN_PROMPT:
            lines.append(f"（另有 {len(issues) - MAX_ISSUES_IN_PROMPT} 条低优先级问题从略）")
            lines.append("")
    else:
        lines.append("当前范围内未发现达到判定阈值的问题。")
        lines.append("")
    lines.extend(["## 三、店铺横向对比", ""])
    if comparison:
        lines.append("| 店铺 | 平台 | 健康分 | SKU 数 | 严重问题 | 关注问题 | 近 7 日销售额 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for row in comparison:
            lines.append(
                f"| {row['shop_name']} | {row['platform_label']} | {row['health_score']} | "
                f"{row['product_count']} | {row['critical_issues']} | {row['warning_issues']} | "
                f"{_fmt_money(row['revenue_7d'])} |"
            )
        lines.append("")
    lines.extend(
        [
            "## 四、口径与边界声明",
            "",
            "- 预计损失为排序用估算值，口径已在每条问题旁注明，不是财务实际损失；",
            "- 售后类问题因演示数据不含订单金额，按客单价假设估算；",
            "- 健康分与问题判定阈值见服务端指标口径，算法版本变更时历史报告快照不变；",
            "- 本报告为只读诊断输出，不构成任何平台写操作指令。",
        ]
    )
    return "\n".join(lines)


def _build_ai_prompt(overview: dict) -> str:
    health = overview["health"]
    payload = {
        "scope": overview["shop_id"],
        "is_demo": overview["is_demo"],
        "health": {
            "score": health["score"],
            "algorithm_version": health["algorithm_version"],
            "components": [
                {"label": item["label"], "score": item["score"], "detail": item["detail"]}
                for item in health["components"]
            ],
        },
        "issues": [
            {
                "title": issue["title"],
                "severity": issue["severity"],
                "confidence": issue["confidence"],
                "detail": issue["detail"],
                "evidence": issue["evidence"],
                "estimated_loss": issue["estimated_loss"],
                "loss_note": issue["loss_note"],
                "urgency": issue["urgency"],
                "recommendation": issue["recommendation"],
            }
            for issue in overview["issues"][:MAX_ISSUES_IN_PROMPT]
        ],
        "comparison": overview["comparison"],
    }
    return (
        "请基于以下经营诊断数据生成一份中文诊断报告。硬性要求："
        "1. 只能引用上面提供的数据点，禁止编造或推算任何数字；"
        "2. 内容必须区分【事实】（有证据的结论）、【推测】（合理推断，需标注依据）、"
        "【建议】（运营动作，标注是否涉及写操作需人工确认）；"
        "3. 预计损失必须照抄口径说明，不得改述为实际损失；"
        "4. 不输出任何要求直接执行平台写操作的指令；"
        "5. 使用 Markdown，包含健康分总览、重点问题、店铺对比、边界声明四节。\n\n"
        f"诊断数据 JSON：\n{payload}"
    )


def generate_report(db: Session, organization_id: str, shop_id: str) -> dict:
    """生成诊断报告（优先真实模型，失败或未配置时降级模板），并落快照。"""
    overview = get_overview(db, shop_id)
    settings = get_settings()
    config = _resolve_ai_config(db, organization_id)

    source = "template"
    model_id: str | None = None
    content = render_template_report(overview)

    if config is not None and settings.ai_live_generation_enabled:
        try:
            provider = get_provider(config.provider_id)
            content = asyncio.run(
                generate_text(
                    provider,
                    config.base_url,
                    api_key_for(config),
                    config.selected_model or "",
                    _build_ai_prompt(overview),
                    "report",
                )
            )
            source = "ai"
            model_id = config.selected_model
        except (AiGenerationError, ValueError) as exc:
            # 模型失败不阻塞报告：降级模板并在文首如实说明
            content = (
                f"> 注意：真实模型生成失败（{exc}），已自动降级为规则模板报告。\n\n"
                + content
            )

    now = datetime.now(SHANGHAI)
    report = DiagnosticReportModel(
        id=f"diag-report-{uuid4().hex[:12]}",
        organization_id=organization_id,
        shop_id=shop_id,
        title=f"经营诊断报告（{shop_id}）",
        source=source,
        model_id=model_id,
        content=content,
        snapshot={
            "generated_at": overview["generated_at"].isoformat(),
            "data_source": overview["data_source"],
            "health": overview["health"],
            "issues": overview["issues"],
            "comparison": overview["comparison"],
        },
        is_demo=overview["is_demo"],
        created_at=now,
    )
    db.add(report)
    db.commit()
    return _to_payload(report)


def _to_payload(model: DiagnosticReportModel) -> dict:
    return {
        "id": model.id,
        "shop_id": model.shop_id,
        "title": model.title,
        "source": model.source,
        "model_id": model.model_id,
        "content": model.content,
        "snapshot": model.snapshot,
        "is_demo": model.is_demo,
        "created_at": model.created_at,
    }


def list_reports(db: Session, organization_id: str, limit: int = 20) -> list[dict]:
    rows = db.scalars(
        select(DiagnosticReportModel)
        .where(DiagnosticReportModel.organization_id == organization_id)
        .order_by(desc(DiagnosticReportModel.created_at))
        .limit(limit)
    ).all()
    return [
        {
            "id": row.id,
            "shop_id": row.shop_id,
            "title": row.title,
            "source": row.source,
            "model_id": row.model_id,
            "is_demo": row.is_demo,
            "created_at": row.created_at,
        }
        for row in rows
    ]


def get_report(db: Session, organization_id: str, report_id: str) -> dict | None:
    row = db.scalar(
        select(DiagnosticReportModel).where(
            DiagnosticReportModel.id == report_id,
            DiagnosticReportModel.organization_id == organization_id,
        )
    )
    if row is None:
        return None
    return _to_payload(row)
