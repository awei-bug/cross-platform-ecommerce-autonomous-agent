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

/** 宿主后台的 origin，用于 postMessage 的 targetOrigin 白名单。 */
export const UNIFIED_HOST_ORIGIN = new URL(UNIFIED_LOGIN_URL).origin

/**
 * 会话失效时导航到统一登录页。内嵌在 iframe 时必须操作顶层窗口，
 * 否则登录页会被塞进 iframe，形成「框里再套一个登录框」。
 */
export function redirectToUnifiedLogin(fullPath: string): false {
  const hostRoute = '/module_cross'
  const loginUrl = new URL(UNIFIED_LOGIN_URL)
  loginUrl.searchParams.set(UNIFIED_LOGIN_REDIRECT_PARAM, hostRoute)
  // 保留子应用深链，登录后由宿主回传给 iframe，避免一律落到模块首页。
  loginUrl.searchParams.set('module_state', fullPath)
  if (window.top && window.top !== window.self) {
    window.top.location.assign(loginUrl.toString())
  } else {
    window.location.assign(loginUrl.toString())
  }
  return false
}

/** 主动登出：内嵌时通知宿主统一处理，独立打开时才自行跳转。 */
export function notifyUnifiedLogout(): void {
  if (window.parent !== window.self) {
    window.parent.postMessage({ type: 'unified:need-login' }, UNIFIED_HOST_ORIGIN)
  } else {
    window.location.assign(UNIFIED_LOGIN_URL)
  }
}
