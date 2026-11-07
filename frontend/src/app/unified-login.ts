/**
 * 全平台唯一的登录页（云购商家后台）。跨境工作台不再有自己的登录页：
 * 未认证时一律跳转到该地址，登录成功后由统一登录页带 token 回跳。
 */
export const UNIFIED_LOGIN_URL = 'http://127.0.0.1:8080/admin/login'

/** 统一登录页回跳参数名，与云购后台约定。 */
export const UNIFIED_LOGIN_REDIRECT_PARAM = 'redirect'

/** 回跳地址可能带 token，放在查询串里由 session store 消费后立即抹掉。 */
export const SESSION_HANDOFF_PARAM = 'access_token'

export function unifiedLoginRedirect(fullPath: string, origin?: string): string {
  const base = origin ?? (typeof window === 'undefined' ? '' : window.location.origin)
  const target = `${base}${fullPath.startsWith('/') ? fullPath : `/${fullPath}`}`
  return `${UNIFIED_LOGIN_URL}?${UNIFIED_LOGIN_REDIRECT_PARAM}=${encodeURIComponent(target)}`
}

/** 把浏览器整页送到统一登录页；返回 false 供路由守卫中断导航。 */
export function redirectToUnifiedLogin(fullPath: string): false {
  window.location.assign(unifiedLoginRedirect(fullPath))
  return false
}
