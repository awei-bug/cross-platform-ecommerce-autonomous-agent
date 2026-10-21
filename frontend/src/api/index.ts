import type {
  ProductSyncResponse,
  DisconnectResponse,
  OAuthAuthorizationResponse,
  ConnectorPlatform,
  ConnectorStatus,
  AdOverview,
  AgentRun,
  AgentRunListItem,
  AlertItem,
  BatchActionRequest,
  BatchJob,
  CompetitorItem,
  CompetitorImportRequest,
  CompetitorImportResult,
  ContentConnectAuthorize,
  ContentConnectStatus,
  ContentDisconnect,
  ContentPublish,
  ContentPublishCreate,
  ContentPublishList,
  DashboardOverview,
  Diagnosis,
  DiagnosticExportJob,
  DiagnosticOverview,
  DiagnosticReport,
  DiagnosticReportListItem,
  AutomationOverview,
  AutomationRule,
  AutomationRun,
  AutomationTask,
  LoginResponse,
  OrderActionJob,
  OrderActionRequest,
  OrderAuditEntry,
  OrderDetail,
  OrderListResponse,
  OrderQuery,
  PlatformCapability,
  ProductDetail,
  ProductListResponse,
  ProductQuery,
  CampaignStatus,
  Platform,
  SearchResult,
  UserProfile,
  WorkspaceBootstrap,
  ReviewOverview,
  ReviewTicket,
  ReviewTicketStatus,
  ReviewRating,
  ReportOverview,
  ReportExportJob,
  ReportNote,
  ReportTemplateType,
  ReportFormat,
  AiProviderCatalogItem,
  AiConfigurationListResponse,
  AiConfiguration,
  AiConnectionTestResponse,
  AiModelProbeResponse,
  AssetListResponse,
  AssetItem,
  AssetQualityCheckResult,
  AssetType,
  GenerationJob,
  OpsMetrics,
  OpsSweepResult,
  OpsTask,
} from '../types/api'
import { apiRequest, apiRequestBlob } from './http'

export const authApi = {
  login(account: string, password: string) {
    return apiRequest<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ account, password }),
    })
  },
  me(token: string) {
    return apiRequest<UserProfile>('/auth/me', { token })
  },
}

export const workspaceApi = {
  bootstrap(token: string) {
    return apiRequest<WorkspaceBootstrap>('/workspace/bootstrap', { token })
  },
  alerts(token: string, unreadOnly = false) {
    return apiRequest<AlertItem[]>(`/workspace/alerts?unread_only=${unreadOnly}`, { token })
  },
  setAlertRead(token: string, alertId: string, isRead: boolean) {
    return apiRequest<AlertItem>(`/workspace/alerts/${encodeURIComponent(alertId)}`, {
      token,
      method: 'PATCH',
      body: JSON.stringify({ is_read: isRead }),
    })
  },
  readAllAlerts(token: string) {
    return apiRequest<{ changed: number }>('/workspace/alerts/read-all', {
      token,
      method: 'POST',
    })
  },
  capabilities(token: string, shopId: string) {
    return apiRequest<PlatformCapability[]>(
      `/workspace/capabilities?shop_id=${encodeURIComponent(shopId)}`,
      { token },
    )
  },
  search(token: string, keyword: string) {
    return apiRequest<SearchResult[]>(`/search?q=${encodeURIComponent(keyword)}`, { token })
  },
}

export const productApi = {
  list(token: string, query: ProductQuery) {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(query)) {
      if (value !== '' && value !== undefined) params.set(key, String(value))
    }
    return apiRequest<ProductListResponse>(`/products?${params.toString()}`, { token })
  },
  detail(token: string, productId: string) {
    return apiRequest<ProductDetail>(`/products/${encodeURIComponent(productId)}`, { token })
  },
  createBatchJob(token: string, request: BatchActionRequest) {
    return apiRequest<BatchJob>('/products/batch-actions', {
      token,
      method: 'POST',
      body: JSON.stringify(request),
    })
  },
  job(token: string, jobId: string) {
    return apiRequest<BatchJob>(`/products/jobs/${encodeURIComponent(jobId)}`, { token })
  },
}

export const dashboardApi = {
  overview(token: string, shopId: string) {
    return apiRequest<DashboardOverview>(
      `/dashboard/overview?shop_id=${encodeURIComponent(shopId)}`,
      { token },
    )
  },
}

export const automationApi = {
  overview(token: string) {
    return apiRequest<AutomationOverview>('/automation', { token })
  },
  updateRule(
    token: string,
    ruleId: string,
    request: { is_enabled?: boolean; mode?: 'suggest' | 'approval_required' | 'auto' },
  ) {
    return apiRequest<AutomationRule>(`/automation/rules/${encodeURIComponent(ruleId)}`, {
      token,
      method: 'PATCH',
      body: JSON.stringify(request),
    })
  },
  updateTask(
    token: string,
    taskId: string,
    request: {
      status?: 'pending' | 'in_progress' | 'completed' | 'dismissed'
      assignee?: string | null
    },
  ) {
    return apiRequest<AutomationTask>(`/automation/tasks/${encodeURIComponent(taskId)}`, {
      token,
      method: 'PATCH',
      body: JSON.stringify(request),
    })
  },
  runRule(token: string, ruleId: string) {
    return apiRequest<AutomationRun>(`/automation/rules/${encodeURIComponent(ruleId)}/runs`, {
      token,
      method: 'POST',
      body: JSON.stringify({ confirm: true }),
    })
  },
}

export const campaignApi = {
  overview(
    token: string,
    query: {
      shop_id: string
      platform?: Platform
      account_id?: string
      status?: CampaignStatus
      q?: string
    },
  ) {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(query)) {
      if (value !== '' && value !== undefined) params.set(key, String(value))
    }
    return apiRequest<AdOverview>(`/campaigns?${params.toString()}`, { token })
  },
}

export const reportApi = {
  overview(
    token: string,
    query: { shop_id: string; template_id: ReportTemplateType; metrics?: string[] },
  ) {
    const params = new URLSearchParams({ shop_id: query.shop_id, template_id: query.template_id })
    if (query.metrics?.length) params.set('metrics', query.metrics.join(','))
    return apiRequest<ReportOverview>(`/reports?${params.toString()}`, { token })
  },
  createExport(
    token: string,
    request: {
      template_id: ReportTemplateType
      format: ReportFormat
      shop_id: string
      start_date: string
      end_date: string
      metrics: string[]
    },
  ) {
    return apiRequest<ReportExportJob>('/reports/exports', {
      token,
      method: 'POST',
      body: JSON.stringify(request),
    })
  },
  createNote(
    token: string,
    request: {
      template_id: ReportTemplateType
      title: string
      conclusion: string
      next_actions: string
    },
  ) {
    return apiRequest<ReportNote>('/reports/notes', {
      token,
      method: 'POST',
      body: JSON.stringify(request),
    })
  },
  downloadExport(token: string, exportId: string) {
    return apiRequestBlob(`/reports/exports/${encodeURIComponent(exportId)}/download`, { token })
  },
}
export const reviewApi = {
  overview(
    token: string,
    query: {
      shop_id: string
      platform?: Platform
      product_id?: string
      rating?: ReviewRating
      q?: string
      ticket_status?: ReviewTicketStatus
    },
  ) {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(query)) {
      if (value !== '' && value !== undefined) params.set(key, String(value))
    }
    return apiRequest<ReviewOverview>(`/reviews?${params.toString()}`, { token })
  },
  updateTicket(
    token: string,
    request: {
      review_id: string
      assignee: string
      status: ReviewTicketStatus
      reply_draft: string
      follow_up_note: string
    },
  ) {
    return apiRequest<ReviewTicket>('/reviews/tickets', {
      token,
      method: 'POST',
      body: JSON.stringify(request),
    })
  },
}
export const orderApi = {
  list(token: string, query: OrderQuery) {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(query)) {
      if (value !== '' && value !== undefined) params.set(key, String(value))
    }
    return apiRequest<OrderListResponse>(`/orders?${params.toString()}`, { token })
  },
  detail(token: string, orderId: string) {
    return apiRequest<OrderDetail>(`/orders/${encodeURIComponent(orderId)}`, { token })
  },
  createActionJob(token: string, request: OrderActionRequest) {
    return apiRequest<OrderActionJob>('/orders/actions', {
      token,
      method: 'POST',
      body: JSON.stringify(request),
    })
  },
  job(token: string, jobId: string) {
    return apiRequest<OrderActionJob>(`/orders/jobs/${encodeURIComponent(jobId)}`, { token })
  },
  audit(token: string, orderId?: string) {
    const query = orderId ? `?order_id=${encodeURIComponent(orderId)}` : ''
    return apiRequest<OrderAuditEntry[]>(`/orders/audit${query}`, { token })
  },
}

export const aiApi = {
  providers(token: string) {
    return apiRequest<AiProviderCatalogItem[]>('/ai/providers', { token })
  },
  configurations(token: string) {
    return apiRequest<AiConfigurationListResponse>('/ai/configurations', { token })
  },
  createConfiguration(
    token: string,
    request: {
      provider_id: string
      display_name?: string
      base_url?: string
      api_key?: string
      selected_model?: string
    },
  ) {
    return apiRequest<AiConfiguration>('/ai/configurations', {
      token,
      method: 'POST',
      body: JSON.stringify(request),
    })
  },
  updateConfiguration(
    token: string,
    id: string,
    request: {
      display_name?: string
      base_url?: string
      api_key?: string
      selected_model?: string
      is_enabled?: boolean
    },
  ) {
    return apiRequest<AiConfiguration>(`/ai/configurations/${encodeURIComponent(id)}`, {
      token,
      method: 'PATCH',
      body: JSON.stringify(request),
    })
  },
  probeModel(token: string, id: string, modelId?: string | null) {
    return apiRequest<AiModelProbeResponse>(`/ai/configurations/${encodeURIComponent(id)}/probe`, {
      token,
      method: 'POST',
      body: JSON.stringify(modelId ? { model_id: modelId } : {}),
    })
  },
  testConfiguration(token: string, id: string) {
    return apiRequest<AiConnectionTestResponse>(
      `/ai/configurations/${encodeURIComponent(id)}/test`,
      { token, method: 'POST' },
    )
  },
  deleteConfiguration(token: string, id: string) {
    return apiRequest<void>(`/ai/configurations/${encodeURIComponent(id)}`, {
      token,
      method: 'DELETE',
    })
  },
}

export const assetApi = {
  list(token: string, assetType?: AssetType) {
    const suffix = assetType ? `?asset_type=${encodeURIComponent(assetType)}` : ''
    return apiRequest<AssetListResponse>(`/assets${suffix}`, { token })
  },
  create(
    token: string,
    request: {
      title: string
      asset_type: AssetType
      content: string
      product_id?: string
      tags?: string[]
    },
  ) {
    return apiRequest<AssetItem>('/assets', {
      token,
      method: 'POST',
      body: JSON.stringify(request),
    })
  },
  upload(
    token: string,
    file: File,
    request: { title?: string; asset_type?: AssetType; product_id?: string; tags?: string[] } = {},
  ) {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(request)) {
      if (value === undefined || value === '') continue
      params.set(key, Array.isArray(value) ? value.join(',') : value)
    }
    return apiRequest<AssetItem>(`/assets/uploads?${params.toString()}`, {
      token,
      method: 'POST',
      headers: {
        'Content-Type': file.type || 'application/octet-stream',
        'X-Filename': encodeURIComponent(file.name),
      },
      body: file,
    })
  },
  preview(token: string, versionId: string) {
    return apiRequestBlob(`/assets/versions/${encodeURIComponent(versionId)}/preview`, { token })
  },
  recheckQuality(token: string, versionId: string) {
    return apiRequest<AssetQualityCheckResult>(
      `/assets/versions/${encodeURIComponent(versionId)}/quality-checks`,
      { token, method: 'POST' },
    )
  },
  createGenerationJob(
    token: string,
    request: {
      asset_id?: string
      asset_type: AssetType
      prompt: string
      configuration_id?: string
      model_id?: string
    },
  ) {
    return apiRequest<GenerationJob>('/assets/generation-jobs', {
      token,
      method: 'POST',
      body: JSON.stringify(request),
    })
  },
  generationJob(token: string, id: string) {
    return apiRequest<GenerationJob>(`/assets/generation-jobs/${encodeURIComponent(id)}`, { token })
  },
  confirmVersion(token: string, assetId: string, versionId: string) {
    return apiRequest<AssetItem>(
      `/assets/${encodeURIComponent(assetId)}/versions/${encodeURIComponent(versionId)}/confirm`,
      { token, method: 'POST' },
    )
  },
}

export const diagnosticsApi = {
  overview(token: string, shopId: string) {
    const params = new URLSearchParams({ shop_id: shopId })
    return apiRequest<DiagnosticOverview>(`/diagnostics/overview?${params.toString()}`, { token })
  },
  createReport(token: string, shopId: string) {
    const params = new URLSearchParams({ shop_id: shopId })
    return apiRequest<DiagnosticReport>(`/diagnostics/reports?${params.toString()}`, {
      token,
      method: 'POST',
    })
  },
  reports(token: string) {
    return apiRequest<DiagnosticReportListItem[]>('/diagnostics/reports', { token })
  },
  report(token: string, reportId: string) {
    return apiRequest<DiagnosticReport>(`/diagnostics/reports/${encodeURIComponent(reportId)}`, {
      token,
    })
  },
  createExport(token: string, reportId: string, format: 'pdf' | 'xlsx') {
    const params = new URLSearchParams({ format })
    return apiRequest<DiagnosticExportJob>(
      `/diagnostics/reports/${encodeURIComponent(reportId)}/exports?${params.toString()}`,
      { token, method: 'POST' },
    )
  },
  downloadExport(token: string, exportId: string) {
    return apiRequestBlob(`/diagnostics/exports/${encodeURIComponent(exportId)}/download`, {
      token,
    })
  },
}

export const agentApi = {
  createRun(token: string, request: { goal: string; shop_ids?: string[] }) {
    return apiRequest<AgentRun>('/agent/runs', {
      token,
      method: 'POST',
      body: JSON.stringify(request),
    })
  },
  runs(token: string) {
    return apiRequest<AgentRunListItem[]>('/agent/runs', { token })
  },
  run(token: string, runId: string) {
    return apiRequest<AgentRun>(`/agent/runs/${encodeURIComponent(runId)}`, { token })
  },
  decide(
    token: string,
    runId: string,
    diagnosisId: string,
    request: { decision: 'approve' | 'reject'; note?: string },
  ) {
    return apiRequest<Diagnosis>(
      `/agent/runs/${encodeURIComponent(runId)}/diagnoses/${encodeURIComponent(diagnosisId)}/decision`,
      {
        token,
        method: 'POST',
        body: JSON.stringify(request),
      },
    )
  },
  competitors(token: string, query: { category?: string; q?: string } = {}) {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(query)) {
      if (value) params.set(key, value)
    }
    return apiRequest<CompetitorItem[]>(`/agent/competitors?${params.toString()}`, { token })
  },
  createCompetitor(
    token: string,
    request: {
      category?: string
      title: string
      price: number
      selling_points?: string[]
      review_pain_points?: string[]
      platform_label?: string
    },
  ) {
    return apiRequest<CompetitorItem>('/agent/competitors', {
      token,
      method: 'POST',
      body: JSON.stringify(request),
    })
  },
  importTaobaoke(token: string, request: CompetitorImportRequest) {
    return apiRequest<CompetitorImportResult>('/agent/competitors/import-taobaoke', {
      token,
      method: 'POST',
      body: JSON.stringify(request),
    })
  },
}

export const contentStudioApi = {
  connectStatus(token: string) {
    return apiRequest<ContentConnectStatus>('/content-studio/connect/status', { token })
  },
  authorize(token: string) {
    return apiRequest<ContentConnectAuthorize>('/content-studio/connect/authorize', {
      token,
      method: 'POST',
    })
  },
  disconnect(token: string) {
    return apiRequest<ContentDisconnect>('/content-studio/connect/disconnect', {
      token,
      method: 'POST',
    })
  },
  createDraft(token: string, request: ContentPublishCreate) {
    return apiRequest<ContentPublish>('/content-studio/publishes', {
      token,
      method: 'POST',
      body: JSON.stringify(request),
    })
  },
  publishes(token: string) {
    return apiRequest<ContentPublishList>('/content-studio/publishes', { token })
  },
  publish(token: string, publishId: string) {
    return apiRequest<ContentPublish>(
      `/content-studio/publishes/${encodeURIComponent(publishId)}/publish`,
      { token, method: 'POST' },
    )
  },
}

export const opsApi = {
  metrics(token: string) {
    return apiRequest<OpsMetrics>('/ops/metrics', { token })
  },
  tasks(token: string, query: { kind?: string; status?: string } = {}) {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(query)) {
      if (value) params.set(key, value)
    }
    const suffix = params.toString() ? `?${params.toString()}` : ''
    return apiRequest<OpsTask[]>(`/ops/tasks${suffix}`, { token })
  },
  sweep(token: string) {
    return apiRequest<OpsSweepResult>('/ops/tasks/sweep', { token, method: 'POST' })
  },
  retry(token: string, kind: string, taskId: string) {
    return apiRequest<OpsTask>(
      `/ops/tasks/${encodeURIComponent(kind)}/${encodeURIComponent(taskId)}/retry`,
      { token, method: 'POST' },
    )
  },
  discard(token: string, kind: string, taskId: string) {
    return apiRequest<OpsTask>(
      `/ops/tasks/${encodeURIComponent(kind)}/${encodeURIComponent(taskId)}/discard`,
      { token, method: 'POST' },
    )
  },
}

export const integrationApi = {
  connectors(token: string) {
    return apiRequest<ConnectorStatus[]>('/integrations/connectors', { token })
  },
  status(token: string, platform: ConnectorPlatform) {
    return apiRequest<ConnectorStatus>(`/integrations/${platform}/status`, { token })
  },
  authorize(token: string, platform: ConnectorPlatform) {
    return apiRequest<OAuthAuthorizationResponse>(`/integrations/${platform}/authorize`, {
      token,
      method: 'POST',
    })
  },
  disconnect(token: string, platform: ConnectorPlatform) {
    return apiRequest<DisconnectResponse>(`/integrations/${platform}/disconnect`, {
      token,
      method: 'POST',
    })
  },
  // 目前仅抖店实现了真实商品同步；其它平台调用会得到 404，由页面侧控制入口可见性。
  syncProducts(token: string, platform: ConnectorPlatform) {
    return apiRequest<ProductSyncResponse>(`/integrations/${platform}/sync`, {
      token,
      method: 'POST',
    })
  },
}
