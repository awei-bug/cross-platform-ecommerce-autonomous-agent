from app.workers.celery_app import celery_app


def test_celery_registers_operation_tasks() -> None:
    celery_app.loader.import_default_modules()

    assert "operations.process_product_batch" in celery_app.tasks
    assert "operations.process_order_action" in celery_app.tasks
