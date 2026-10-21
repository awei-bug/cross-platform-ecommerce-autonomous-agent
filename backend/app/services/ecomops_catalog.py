"""Versioned specialist contracts and dependency graphs, independent of transport."""

AGENTS = [
    ("orchestrator", "总调度 Agent", "任务分发、状态同步、冲突仲裁与资源优先级"),
    ("market", "市场调研 Agent", "趋势、竞品、需求痛点与品类预筛"),
    ("selection", "选品决策 Agent", "五维评分、landed cost 与备货建议"),
    ("listing", "商品信息 Agent", "多语言 Listing、素材要求与版本迭代"),
    ("marketing", "营销推广 Agent", "预算分配、投放计划、活动与效果优化"),
    ("service", "智能客服 Agent", "咨询草稿、售后分流与评论反馈"),
    ("fulfillment", "履约协同 Agent", "订单校验、库存补货与物流异常"),
    ("compliance", "合规风控 Agent", "五维规则、分级拦截与强制人工审核"),
    ("analytics", "数据分析 Agent", "指标计算、根因证据与绩效复盘"),
    ("platform", "平台对接 Agent", "官方连接器、同步心跳、限流与授权报告"),
    ("governance", "数据治理 Agent", "去重、SKU 标准化、币种与术语映射"),
]

# key, specialist, title, dependency keys. Independent nodes are Celery group members.
WORKFLOWS = {
    "initialization": (
        "初始化与基础配置",
        [
            ("connections", "platform", "店铺连通性与六类同步通道检查", []),
            ("governance", "governance", "基础数据治理检查", ["connections"]),
            ("roles", "orchestrator", "角色与协同权限配置", ["governance"]),
            ("rules", "compliance", "合规规则库与响应配置", ["roles"]),
        ],
    ),
    "selection": (
        "市场调研与选品",
        [
            ("market", "market", "市场趋势与竞品证据收集", []),
            ("precheck", "compliance", "候选品类合规预校验", []),
            ("cost", "fulfillment", "供应链与物流成本测算", []),
            ("evaluate", "selection", "五维评分与利润测算", ["market", "precheck", "cost"]),
            ("listing_copy", "listing", "制作 Listing 草稿", ["evaluate"]),
            ("stock_plan", "fulfillment", "生成供应链备货工单", ["evaluate"]),
            ("warmup", "marketing", "制定营销预热计划", ["evaluate"]),
            (
                "handoff",
                "orchestrator",
                "汇总三个分支与质量标准",
                ["listing_copy", "stock_plan", "warmup"],
            ),
        ],
    ),
    "listing": (
        "Listing 草稿与合规审核",
        [
            ("listing_copy", "listing", "多语言文案与关键词草稿", []),
            ("listing_check", "compliance", "Listing 文案与版权证据审核", ["listing_copy"]),
        ],
    ),
    "marketing": (
        "营销方案与预算检查",
        [
            ("marketing_plan", "marketing", "渠道预算与 ROI 目标", []),
            ("marketing_check", "compliance", "宣传与活动合规校验", ["marketing_plan"]),
            ("ad_monitor", "marketing", "核对消耗快照与预算上限", ["marketing_check"]),
        ],
    ),
    "service": (
        "客服草稿与售后审核",
        [
            ("service_context", "service", "识别意图并读取订单产品知识", []),
            ("service_decide", "service", "售后分流与回复草稿", ["service_context"]),
            ("service_check", "compliance", "客服内容与退款权限检查", ["service_decide"]),
            ("feedback", "selection", "沉淀评论痛点与产品改进工单", ["service_decide"]),
        ],
    ),
    "fulfillment": (
        "履约校验与补货建议",
        [
            ("order_check", "fulfillment", "订单地址与库存校验", []),
            ("trade_check", "compliance", "贸易管制与目的地规则检查", ["order_check"]),
            ("warehouse", "fulfillment", "仓储与物流渠道指令草案", ["trade_check"]),
            ("inventory", "fulfillment", "安全库存监控与补货预警", ["order_check"]),
            ("tracking", "fulfillment", "物流异常与客服协同工单", ["order_check"]),
        ],
    ),
    "analytics": (
        "数据复盘与策略迭代",
        [
            ("aggregate", "analytics", "全链路指标聚合", []),
            ("diagnose", "analytics", "问题诊断与根因证据", ["aggregate"]),
            ("strategy", "orchestrator", "拆解全局策略与责任工单", ["diagnose"]),
        ],
    ),
}

PLATFORMS = [
    {"id": key, "name": name, "status": "adapter_required", "live": False,
     "official_docs": url,
     "channels": ["products", "orders", "service", "logistics", "ads", "reviews"],
     "message": "尚未实现官方连接器；授权、心跳、限流和双向同步均待接入验证"}
    for key, name, url in [
        ("amazon", "Amazon", "https://developer-docs.amazon.com/sp-api/"),
        ("aliexpress", "AliExpress", "https://open.aliexpress.com/"),
        ("temu", "Temu", "https://partner.temu.com/"),
        ("shopee", "Shopee", "https://open.shopee.com/"),
        ("tiktok_shop", "TikTok Shop", "https://partner.tiktokshop.com/docv2"),
    ]
]

# Guards for persisted runs created before the business-value cleanup.
# New DAGs contain only executable local tools; these never perform external writes.
EXTERNAL_STEPS = {
    "publish",
    "ad_execute",
    "activity",
    "service_execute",
    "ship",
    "verify_expansion",
}

RETIRED_WORKFLOWS = {"iteration", "expansion"}
