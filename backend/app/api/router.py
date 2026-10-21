from fastapi import APIRouter

from app.api.routes import (
    agent,
    ai,
    assets,
    auth,
    automation,
    campaigns,
    content_studio,
    dashboard,
    diagnostics,
    ecomops,
    integrations,
    ops,
    orders,
    products,
    reports,
    reviews,
    search,
    workspace,
)

api_router = APIRouter()
api_router.include_router(ecomops.router)
api_router.include_router(auth.router)
api_router.include_router(agent.router)
api_router.include_router(diagnostics.router)
api_router.include_router(ops.router)
api_router.include_router(content_studio.router)
api_router.include_router(ai.router)
api_router.include_router(assets.router)
api_router.include_router(automation.router)
api_router.include_router(workspace.router)
api_router.include_router(search.router)
api_router.include_router(products.router)
api_router.include_router(reports.router)
api_router.include_router(reviews.router)
api_router.include_router(orders.router)
api_router.include_router(dashboard.router)
api_router.include_router(campaigns.router)

api_router.include_router(integrations.router)
