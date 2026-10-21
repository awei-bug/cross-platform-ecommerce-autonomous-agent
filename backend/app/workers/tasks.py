from app.db.session import session_scope
from app.workers.celery_app import celery_app


@celery_app.task(name="ecomops.dispatch")
def dispatch_ecom_run(organization_id: str, run_id: str) -> None:
    from app.services.ecomops_service import dispatch_run

    dispatch_run(organization_id, run_id)


@celery_app.task(name="ecomops.execute_step")
def execute_ecom_step(organization_id: str, run_id: str, task_id: str) -> None:
    from app.services.ecomops_service import execute_step

    execute_step(organization_id, run_id, task_id)


@celery_app.task(name="ecomops.tick")
def tick_ecomops(organization_id: str | None = None) -> dict:
    from app.services.ecomops_service import recover_and_tick

    return recover_and_tick(organization_id)


@celery_app.task(name="operations.process_product_batch")
def process_product_batch(job_id: str) -> None:
    from app.services.product_repository import execute_batch_job

    with session_scope() as db:
        execute_batch_job(db, job_id)


@celery_app.task(name="operations.process_order_action")
def process_order_action(job_id: str) -> None:
    from app.services.order_repository import execute_action_job

    with session_scope() as db:
        execute_action_job(db, job_id)


@celery_app.task(name="operations.process_generation_job")
def process_generation_job(job_id: str) -> None:
    from app.services.asset_repository import execute_generation_job

    with session_scope() as db:
        execute_generation_job(db, job_id)


@celery_app.task(name="agent.execute_run")
def execute_agent_run(run_id: str) -> None:
    from app.services.agent_orchestrator import execute_run

    execute_run(run_id)


@celery_app.task(name="ops.sweep_stale_tasks")
def sweep_stale_tasks_task() -> None:
    """超时巡检任务入口：生产模式下由调度器周期调用。"""
    from app.services.ops_task_service import sweep_stale_tasks

    with session_scope() as db:
        sweep_stale_tasks(db)
