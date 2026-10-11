from app.db.session import session_scope
from app.workers.celery_app import celery_app


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
