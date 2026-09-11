# 后端

FastAPI 模块化单体，当前阶段提供登录、工作区、告警、平台能力矩阵和跨店铺搜索的 Mock API。

## 命令

```powershell
uv sync --dev
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
uv run ruff check .
uv run pytest
```

演示令牌由登录接口签发；除登录和健康检查外，当前接口均要求 `Bearer demo-access-token`。
