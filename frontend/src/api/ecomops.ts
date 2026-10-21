import { apiRequest } from './http'

export interface EcomTask {
  id: string
  key: string
  agent: string
  title: string
  dependencies: string[]
  status: string
  reason: string
  risk: string
  attempts: number
  output: Record<string, unknown>
}
export interface EcomRun {
  id: string
  title: string
  workflow: string
  status: string
  priority: number
  config_version: number
  created_at: string
  input?: Record<string, unknown>
  tasks?: EcomTask[]
  events?: Array<{ id: string; topic: string; created_at: string; status: string }>
  audits?: Array<{ id: string; actor: string; action: string; note: string; created_at: string }>
}
export interface RiskRule {
  id: string
  dimension: string
  pattern: string
  level: string
  replacement: string
}
export interface EcomPolicy {
  stock_amount_limit: number
  budget_change_limit_pct: number
  refund_limit: number
  selection_min_score: number
  min_margin_pct: number
  max_attempts: number
  rules: RiskRule[]
}
export interface EcomOverview {
  configuration: { version: number; payload: EcomPolicy }
  initialization_ready: boolean
  production_ready: boolean
  data_counts: Record<string, number>
  agents: Array<{ id: string; name: string; responsibility: string }>
  platforms: Array<{ id: string; name: string; message: string; official_docs: string }>
  workflows: Array<{
    id: string
    name: string
    steps: Array<{ key: string; title: string; agent: string; dependencies: string[] }>
  }>
  runs: EcomRun[]
  limitations: string[]
}
export interface EcomSchedule {
  id: string
  workflow: string
  interval_hours: number
  enabled: boolean
  next_run_at: string
}
export interface EcomPerformance {
  agents: Array<{
    id: string
    name: string
    tasks: number
    completion_rate: number | null
    avg_duration_ms: number | null
  }>
  limitation: string
}
export interface EcomRecord {
  id: string
  kind: string
  key: string
  payload: Record<string, unknown>
  source: string
  is_demo: boolean
}

export interface ResearchCollection {
  collection_id: string
  country: string
  category: string
  count: number
}
export interface ResearchCandidate {
  key: string
  title: string
  source_url: string
  price: number | null
  currency: string | null
  collected_at: string
  specifications: Record<string, string>
  popularity_claim: string | null
  ranking: { rank: number; category: string; source_url: string } | null
  max_fixed_cost_at_target_margin: number | null
}
export interface ResearchReport {
  sample_count: number
  ranked_sample_count: number
  candidates: ResearchCandidate[]
  excluded: Array<{ key: string; reason: string }>
  limitations: string[]
}

export const ecomApi = {
  researchCollections: (token: string) =>
    apiRequest<ResearchCollection[]>('/ecomops/research/collections', { token }),
  importResearch: (token: string, body: object) =>
    apiRequest('/ecomops/research/import', { token, method: 'POST', body: JSON.stringify(body) }),
  analyzeResearch: (token: string, body: object) =>
    apiRequest<ResearchReport>('/ecomops/research/analyze', {
      token,
      method: 'POST',
      body: JSON.stringify(body),
    }),
  overview: (token: string) => apiRequest<EcomOverview>('/ecomops/overview', { token }),
  run: (token: string, id: string) => apiRequest<EcomRun>(`/ecomops/runs/${id}`, { token }),
  create: (token: string, body: object) =>
    apiRequest<EcomRun>('/ecomops/runs', { token, method: 'POST', body: JSON.stringify(body) }),
  intervene: (token: string, id: string, body: object) =>
    apiRequest<EcomRun>(`/ecomops/runs/${id}/intervene`, {
      token,
      method: 'POST',
      body: JSON.stringify(body),
    }),
  configure: (token: string, version: number, policy: EcomPolicy) =>
    apiRequest('/ecomops/configuration', {
      token,
      method: 'PUT',
      body: JSON.stringify({ version, policy }),
    }),
  import: (token: string, records: object[]) =>
    apiRequest<{ inserted: number; updated: number; deduplicated: number }>(
      '/ecomops/data/import',
      {
        token,
        method: 'POST',
        body: JSON.stringify({ records }),
      },
    ),
  records: (token: string) => apiRequest<EcomRecord[]>('/ecomops/data', { token }),
  schedules: (token: string) => apiRequest<EcomSchedule[]>('/ecomops/schedules', { token }),
  schedule: (token: string, body: object) =>
    apiRequest('/ecomops/schedules', { token, method: 'POST', body: JSON.stringify(body) }),
  toggleSchedule: (token: string, id: string, enabled: boolean) =>
    apiRequest(`/ecomops/schedules/${id}`, {
      token,
      method: 'PATCH',
      body: JSON.stringify({ enabled }),
    }),
  performance: (token: string) => apiRequest<EcomPerformance>('/ecomops/performance', { token }),
  tick: (token: string) => apiRequest('/ecomops/tick', { token, method: 'POST' }),
}
