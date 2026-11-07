import os

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("DATABASE_AUTO_CREATE", "true")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
# 身份唯一来源是云购会话；单元测试没有云购实例，因此显式打开本地开发回退，
# 让既有业务用例继续覆盖路由逻辑。生产环境（ENVIRONMENT=production）该开关无效。
os.environ.setdefault("DEMO_IDENTITY_FALLBACK_ENABLED", "true")
os.environ.setdefault("ENVIRONMENT", "test")
