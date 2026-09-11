# 前端

Vue 3 + TypeScript + Vite 单页应用，承载一站式多平台电商运营工作台。

## 命令

```powershell
pnpm dev          # 本地开发，/api 代理到 127.0.0.1:8000
pnpm typecheck    # TypeScript 检查
pnpm lint         # ESLint
pnpm test         # Vitest
pnpm build        # 生产构建
```

## 约束

- Pinia 只管理用户、组织、店铺和 UI 上下文；
- TanStack Vue Query 管理服务端状态；
- Element Plus 是底层原语，业务页优先使用项目组件；
- 全局视觉变量位于 `src/styles/tokens.scss`；
- 六个业务模块通过路由懒加载。
