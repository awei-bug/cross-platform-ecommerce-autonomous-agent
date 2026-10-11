import os

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("DATABASE_AUTO_CREATE", "true")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
