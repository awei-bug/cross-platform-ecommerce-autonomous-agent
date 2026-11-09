import os

from cryptography.fernet import Fernet

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("DATABASE_AUTO_CREATE", "true")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
# 身份唯一来源是云购会话；单元测试没有云购实例，因此显式打开本地开发回退，
# 让既有业务用例继续覆盖路由逻辑。生产环境（ENVIRONMENT=production）该开关无效。
os.environ.setdefault("DEMO_IDENTITY_FALLBACK_ENABLED", "true")
os.environ.setdefault("ENVIRONMENT", "test")

# CI 不会加载 backend/.env，TokenCipher 会因缺密钥构造失败，进而让 OAuth
# 连接相关用例拿到 None。测试环境生成一把临时 Fernet 密钥，不触碰生产密钥。
if "TOKEN_ENCRYPTION_KEYS" not in os.environ:
    os.environ["TOKEN_ENCRYPTION_KEYS"] = Fernet.generate_key().decode()
