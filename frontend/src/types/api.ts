export type Platform = 'all' | 'taobao' | 'douyin' | 'pinduoduo'
export type Severity = 'critical' | 'warning' | 'info'
export type CapabilityMode = 'direct' | 'async' | 'redirect' | 'unsupported'
export type ProductStatus = 'online' | 'offline' | 'draft'
export type ProductRisk = 'critical' | 'warning' | 'normal'
export type BatchAction = 'publish' | 'unpublish' | 'update_price' | 'sync'
export type JobStatus = 'queued' | 'running' | 'succeeded' | 'partial' | 'failed'

export interface UserProfile {
  id: string
  name: string
  avatar_url: string | null
  role_name: string
  organization_id: string
  permissions: string[]
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: UserProfile
}

export interface Organization {
  id: string
  name: string
}

export interface Shop {
  id: string
  name: string
  platform: Platform
  platform_label: string
  status: string
  last_synced_at: string
}

export interface WorkspaceContext {
  organization_id: string
  shop_id: string
  platform: Platform
  time_range: string
}

export interface WorkspaceSummary {
  today_sales: number
  paid_orders: number
  active_alerts: number
  pending_tasks: number
  updated_at: string
}

export interface WorkspaceBootstrap {
  organization: Organization
  shops: Shop[]
  context: WorkspaceContext
  summary: WorkspaceSummary
}

export interface AlertItem {
  id: string
  title: string
  description: string
  severity: Severity
  shop_id: string
  shop_name: string
  created_at: string
  is_read: boolean
}

export interface SearchResult {
  id: string
  type: 'sku' | 'order' | 'campaign' | string
  title: string
  subtitle: string
  route: string
}

export interface PlatformCapability {
  key: string
  label: string
  mode: CapabilityMode
  reason: string | null
}

export interface Pagination {
  page: number
  page_size: number
  total: number
}

export interface ProductListItem {
  id: string
  sku: string
  title: string
  platform: Platform
  platform_label: string
  shop_id: string
  shop_name: string
  status: ProductStatus
  risk: ProductRisk
  risk_labels: string[]
  price: number
  cost: number
  stock: number
  sales_7d: number
  revenue_7d: number
  conversion_rate: number
  updated_at: string
}

export interface ProductSummary {
  total: number
  critical: number
  warning: number
  offline: number
  low_stock: number
}

export interface ProductListResponse {
  items: ProductListItem[]
  pagination: Pagination
  summary: ProductSummary
  data_updated_at: string
  is_demo: boolean
}

export interface ProductSpec {
  label: string
  value: string
}

export interface CompetitorSnapshot {
  name: string
  price: number
  sales_7d: number
  difference: string
}

export interface AiSuggestion {
  title: string
  detail: string
  impact: string
  action: string
}

export interface ProductDetail extends ProductListItem {
  category: string
  barcode: string
  specs: ProductSpec[]
  competitors: CompetitorSnapshot[]
  ai_suggestions: AiSuggestion[]
  capability_note: string
  is_demo: boolean
}

export interface ProductQuery {
  shop_id: string
  platform?: Platform
  q?: string
  status?: ProductStatus | ''
  risk?: ProductRisk | ''
  sort_by?: string
  sort_order?: 'asc' | 'desc'
  page?: number
  page_size?: number
}

export interface BatchActionRequest {
  action: BatchAction
  product_ids: string[]
  payload?: Record<string, unknown>
  idempotency_key: string
}

export interface BatchItemResult {
  product_id: string
  sku: string
  success: boolean
  message: string
}

export interface BatchJob {
  id: string
  action: BatchAction
  status: JobStatus
  progress: number
  total: number
  succeeded: number
  failed: number
  created_at: string
  updated_at: string
  results: BatchItemResult[]
  is_demo: boolean
}

export interface DashboardMetric {
  key: string
  label: string
  value: number
  unit: 'currency' | 'integer' | 'percent' | string
  comparison: number
  comparison_label: string
  definition: string
}

export interface TrendPoint {
  date: string
  sales: number
  orders: number
}

export interface DashboardRiskItem {
  id: string
  level: ProductRisk
  title: string
  detail: string
  estimated_loss: number
  deadline: string
  route: string
  shop_name: string
}

export interface OperationTask {
  id: string
  title: string
  owner: string
  status: string
  progress: number
  due_at: string
}

export interface TopProduct {
  id: string
  sku: string
  title: string
  platform: Platform
  platform_label: string
  revenue: number
  sales: number
  trend: number
}

export interface AiBrief {
  headline: string
  summary: string
  evidence: string[]
  actions: string[]
  context_label: string
}

export interface DashboardOverview {
  metrics: DashboardMetric[]
  trend: TrendPoint[]
  risks: DashboardRiskItem[]
  tasks: OperationTask[]
  top_products: TopProduct[]
  ai_brief: AiBrief
  data_updated_at: string
  is_demo: boolean
}

export type AutomationRuleType = 'after_sale_sla' | 'inventory_low' | 'product_quality'
export type AutomationMode = 'suggest' | 'approval_required' | 'auto'
export type AutomationRunStatus = 'succeeded' | 'failed'
export type AutomationTaskStatus = 'pending' | 'in_progress' | 'completed' | 'dismissed'

export interface AutomationRule {
  id: string
  name: string
  rule_type: AutomationRuleType
  description: string
  mode: AutomationMode
  config: Record<string, unknown>
  is_enabled: boolean
  last_run_at: string | null
  created_at: string
  updated_at: string
  is_demo: boolean
}

export interface AutomationMatch {
  task_id: string | null
  entity_id: string
  entity_type: string
  reference: string
  title: string
  severity: string
  reason: string
  suggested_action: string
}

export interface AutomationTask {
  id: string
  run_id: string
  rule_id: string
  entity_id: string
  entity_type: string
  reference: string
  title: string
  severity: string
  reason: string
  suggested_action: string
  status: AutomationTaskStatus
  assignee: string | null
  due_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
  is_demo: boolean
}

export interface AutomationRun {
  id: string
  rule_id: string
  rule_name: string
  status: AutomationRunStatus
  matched_count: number
  task_count: number
  results: AutomationMatch[]
  error_message: string | null
  created_at: string
  completed_at: string | null
  is_demo: boolean
}

export interface AutomationOverview {
  rules: AutomationRule[]
  runs: AutomationRun[]
  tasks: AutomationTask[]
  data_updated_at: string
  is_demo: boolean
}

export type OrderStatus = 'pending_shipment' | 'shipped' | 'completed' | 'closed'
export type AfterSaleStatus =
  | 'none'
  | 'requested'
  | 'merchant_processing'
  | 'buyer_returning'
  | 'refund_processing'
  | 'resolved'
export type OrderRisk = 'critical' | 'warning' | 'normal'
export type OrderAction =
  'remind_ship' | 'approve_refund' | 'reject_refund' | 'send_reply' | 'mark_follow_up'
export type OrderActionStatus = 'queued' | 'running' | 'succeeded' | 'partial' | 'failed'

export interface OrderListItem {
  id: string
  order_no: string
  platform: Platform
  platform_label: string
  shop_id: string
  shop_name: string
  buyer_masked: string
  item_title: string
  sku: string
  quantity: number
  amount: number
  order_status: OrderStatus
  after_sale_status: AfterSaleStatus
  risk: OrderRisk
  risk_reasons: string[]
  sla_deadline: string | null
  remaining_minutes: number | null
  estimated_loss: number
  created_at: string
  updated_at: string
  sensitive_data_masked: boolean
}

export interface OrderSummary {
  total: number
  critical: number
  overdue: number
  due_within_2h: number
  pending_after_sale: number
  pending_shipment: number
  estimated_loss: number
}

export interface OrderListResponse {
  items: OrderListItem[]
  pagination: Pagination
  summary: OrderSummary
  data_updated_at: string
  is_demo: boolean
}

export interface OrderQuery {
  shop_id: string
  platform?: Platform
  q?: string
  status?: OrderStatus | ''
  after_sale_status?: AfterSaleStatus | ''
  risk?: OrderRisk | ''
  sla?: '' | 'overdue' | 'two_hours' | 'today'
  sort_by?: string
  sort_order?: 'asc' | 'desc'
  page?: number
  page_size?: number
}

export interface OrderLine {
  sku: string
  title: string
  quantity: number
  unit_price: number
}

export interface OrderTimelineItem {
  time: string
  title: string
  detail: string
  state: string
}

export interface ConversationMessage {
  id: string
  sender: string
  sender_type: string
  content: string
  sent_at: string
}

export interface AiReplySuggestion {
  id: string
  tone: string
  content: string
  evidence: string[]
}

export interface OrderAuditEntry {
  id: string
  order_id: string
  order_no: string
  action: OrderAction
  action_label: string
  actor: string
  result: string
  note: string
  created_at: string
  is_demo: boolean
}

export interface OrderDetail extends OrderListItem {
  buyer_phone_masked: string
  shipping_address_masked: string
  logistics_company: string | null
  tracking_no_masked: string | null
  lines: OrderLine[]
  timeline: OrderTimelineItem[]
  conversation: ConversationMessage[]
  ai_replies: AiReplySuggestion[]
  available_actions: OrderAction[]
  audit_entries: OrderAuditEntry[]
  capability_note: string
  is_demo: boolean
}

export interface OrderActionRequest {
  action: OrderAction
  order_ids: string[]
  payload?: Record<string, unknown>
  idempotency_key: string
}

export interface OrderActionItemResult {
  order_id: string
  order_no: string
  success: boolean
  message: string
}

export interface OrderActionJob {
  id: string
  action: OrderAction
  status: OrderActionStatus
  progress: number
  total: number
  succeeded: number
  failed: number
  created_at: string
  updated_at: string
  results: OrderActionItemResult[]
  is_demo: boolean
}
export type CampaignStatus = 'running' | 'paused' | 'review'

export interface AdAccount {
  id: string
  name: string
  platform: Platform
  platform_label: string
  shop_id: string
  shop_name: string
  status: string
  spend_7d: number
  budget_7d: number
  roi: number
}

export interface AdCampaign {
  id: string
  account_id: string
  account_name: string
  platform: Platform
  platform_label: string
  shop_id: string
  shop_name: string
  name: string
  status: CampaignStatus
  impressions: number
  clicks: number
  spend: number
  ctr: number
  conversion_rate: number
  conversions: number
  revenue: number
  roi: number
  budget: number
  budget_used: number
  anomaly: boolean
  updated_at: string
}

export interface AdTrendPoint {
  date: string
  spend: number
  revenue: number
  conversions: number
}

export interface BudgetAlert {
  id: string
  account_id: string
  account_name: string
  shop_name: string
  spend: number
  budget: number
  usage_percent: number
  message: string
  severity: string
}

export interface AdRecommendation {
  id: string
  campaign_id: string
  level: string
  title: string
  detail: string
  evidence: string[]
  action: string
}

export interface AdSummary {
  spend: number
  revenue: number
  roi: number
  impressions: number
  clicks: number
  conversions: number
  active_campaigns: number
  anomaly_campaigns: number
}

export interface AdOverview {
  accounts: AdAccount[]
  campaigns: AdCampaign[]
  trend: AdTrendPoint[]
  budget_alerts: BudgetAlert[]
  recommendations: AdRecommendation[]
  summary: AdSummary
  data_updated_at: string
  is_demo: boolean
}

export type ReviewRating = 'positive' | 'neutral' | 'negative'
export type ReviewTicketStatus = 'open' | 'in_progress' | 'resolved'

export interface ReviewProduct {
  id: string
  title: string
  sku: string
  shop_id: string
  shop_name: string
  platform: Platform
  platform_label: string
  monitored: boolean
  review_count: number
  negative_count: number
}

export interface ReviewItem {
  id: string
  product_id: string
  product_title: string
  sku: string
  platform: Platform
  platform_label: string
  shop_id: string
  shop_name: string
  rating: number
  rating_label: ReviewRating
  content: string
  images: string[]
  buyer_nickname: string
  created_at: string
  keywords: string[]
  ticket_id: string | null
  ticket_status: ReviewTicketStatus | null
}

export interface ReviewTicket {
  id: string
  review_id: string
  product_title: string
  shop_name: string
  title: string
  status: ReviewTicketStatus
  assignee: string
  reply_draft: string
  follow_up_note: string
  updated_at: string
  is_demo: boolean
}

export interface SentimentWord {
  word: string
  count: number
  sentiment: ReviewRating
}

export interface ReviewTemplate {
  id: string
  name: string
  scenario: string
  content: string
  tone: string
}

export interface ReviewSummary {
  total: number
  positive: number
  neutral: number
  negative: number
  open_tickets: number
  monitored_products: number
}

export interface ReviewOverview {
  products: ReviewProduct[]
  reviews: ReviewItem[]
  tickets: ReviewTicket[]
  words: SentimentWord[]
  templates: ReviewTemplate[]
  summary: ReviewSummary
  data_updated_at: string
  is_demo: boolean
}

export type ReportTemplateType = 'daily' | 'weekly' | 'monthly' | 'product' | 'ad' | 'after_sale'
export type ReportFormat = 'excel' | 'pdf'

export interface ReportTemplate {
  id: ReportTemplateType
  name: string
  description: string
  category: string
  default_metrics: string[]
}

export interface ReportMetric {
  key: string
  label: string
  value: number
  display_value: string
  change: number
  direction: string
}

export interface ReportTrendPoint {
  date: string
  revenue: number
  orders: number
  spend: number
  refunds: number
}

export interface ReportRow {
  id: string
  name: string
  shop_name: string
  platform_label: string
  revenue: number
  orders: number
  spend: number
  roi: number
  refund_rate: number
}

export interface ReportExportJob {
  id: string
  template_id: ReportTemplateType
  template_name: string
  format: ReportFormat
  status: string
  progress: number
  file_name: string
  created_at: string
  completed_at: string | null
  is_demo: boolean
}

export interface ReportNote {
  id: string
  template_id: ReportTemplateType
  title: string
  conclusion: string
  next_actions: string
  author: string
  created_at: string
  is_demo: boolean
}

export interface ReportOverview {
  templates: ReportTemplate[]
  selected_template: ReportTemplateType
  selected_metrics: string[]
  metrics: ReportMetric[]
  trend: ReportTrendPoint[]
  rows: ReportRow[]
  exports: ReportExportJob[]
  notes: ReportNote[]
  data_updated_at: string
  is_demo: boolean
}

export type AiProviderProtocol = 'openai-compatible' | 'anthropic' | 'gemini' | 'ollama' | 'mock'
export interface AiProviderCatalogItem {
  id: string
  name: string
  protocol: AiProviderProtocol
  description: string
  default_base_url: string
  requires_api_key: boolean
  supports_model_discovery: boolean
  capabilities: string[]
  documentation_url: string | null
}
export interface AiDiscoveredModel {
  id: string
  model_id: string
  display_name: string
  capabilities: string[]
  is_free?: boolean | null
  discovered_at: string
}
export interface AiConfiguration {
  id: string
  provider_id: string
  provider_name: string
  display_name: string
  base_url: string
  api_key_masked: string | null
  selected_model: string | null
  status: 'not_tested' | 'connected' | 'error'
  last_tested_at: string | null
  last_error: string | null
  is_enabled: boolean
  is_demo: boolean
  models: AiDiscoveredModel[]
  created_at: string
  updated_at: string
}
export interface AiConfigurationListResponse {
  items: AiConfiguration[]
  is_demo: boolean
}
export interface AiConnectionTestResponse {
  status: string
  message: string
  configuration: AiConfiguration
  models: AiDiscoveredModel[]
}
export interface AiModelProbeResponse {
  status: string
  model_id: string
  message: string
  preview?: string | null
  latency_ms?: number | null
  is_demo: boolean
}
export type AssetType = 'copy' | 'image' | 'video_script' | 'video' | 'template'
export interface AssetVersion {
  id: string
  version_number: number
  source: string
  content: string
  preview_url: string | null
  object_key: string | null
  content_type: string | null
  file_size: number | null
  quality_status: string
  quality_issues: string[]
  created_at: string
}
export interface AssetItem {
  id: string
  product_id: string | null
  title: string
  asset_type: AssetType
  status: 'draft' | 'review' | 'approved'
  current_version_id: string | null
  tags: string[]
  versions: AssetVersion[]
  is_demo: boolean
  created_at: string
  updated_at: string
}
export interface AssetListResponse {
  items: AssetItem[]
  total: number
  is_demo: boolean
}
export interface GenerationJob {
  id: string
  asset_id: string | null
  asset_type: AssetType
  prompt: string
  model_id: string
  status: string
  progress: number
  result_version_id: string | null
  error_message: string | null
  is_demo: boolean
  created_at: string
  updated_at: string
}

// ---------------------------------------------------------------------------
// 平台连接器（淘宝 / 抖店 / 拼多多）
// ---------------------------------------------------------------------------
export type ConnectorPlatform = Exclude<Platform, 'all'>

export type ConnectorState =
  | 'credentials_required'
  | 'authorization_required'
  | 'adapter_pending'
  | 'ready'
  | 'expired'
  | 'revoked'
  | 'error'

export interface ConnectorStatus {
  platform: ConnectorPlatform
  platform_label: string
  state: ConnectorState
  read_scopes: string[]
  missing_secrets: string[]
  message: string
  platform_user_name: string | null
  platform_shop_id: string | null
  platform_shop_name: string | null
  access_token_expires_at: string | null
  authorized_at: string | null
  last_error: string | null
}

export interface OAuthAuthorizationResponse {
  platform: ConnectorPlatform
  authorization_url: string
  expires_at: string
}

export interface DisconnectResponse {
  platform: ConnectorPlatform
  state: ConnectorState
  disconnected_at: string
}

/** 平台商品真实同步结果。is_live 为 false 表示未真实调用平台 API。 */
export interface ProductSyncResponse {
  platform: ConnectorPlatform
  shop_id: string | null
  shop_name: string | null
  data_source: string
  is_live: boolean
  created: number
  updated: number
  unchanged: number
  total_fetched: number
  warnings: string[]
  synced_at: string
}
