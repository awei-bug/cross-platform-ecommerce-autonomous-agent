Set-Location -LiteralPath 'F:\Python_code\一站式多平台电商运营 AI 工作台\backend'
$env:DATABASE_URL='sqlite+pysqlite:///./data/ops_workbench.db'
$env:DATABASE_AUTO_CREATE='true'
$env:CELERY_TASK_ALWAYS_EAGER='true'
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
