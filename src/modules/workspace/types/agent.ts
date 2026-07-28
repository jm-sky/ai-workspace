export type AgentRunStatus = 'running' | 'completed' | 'failed'

export type AgentStepType = 'model' | 'tool_call' | 'tool_result' | 'guard' | 'step'

export type AgentRoutingReason = 'explicit' | 'session' | 'default'

export interface IAgentSummary {
  key: string
  name: string
  description: string
  isDefault: boolean
  toolProfile: string[]
}

export interface IAgentListResponse {
  agents: IAgentSummary[]
}

export interface IAgentDetail {
  id: string
  key: string
  name: string
  description: string
  systemPrompt: string
  model?: string | null
  effort?: string | null
  toolProfile: string[]
  memoryScopes: string[]
  ragEnabled: boolean
  routingHints: Record<string, unknown>
  isEnabled: boolean
  isDefault: boolean
  createdAt: string
  updatedAt: string
}

export interface IAgentAdminListResponse {
  agents: IAgentDetail[]
}

export interface IAgentCreateRequest {
  key: string
  name: string
  description?: string
  systemPrompt: string
  model?: string | null
  toolProfile?: string[]
  memoryScopes?: string[]
  ragEnabled?: boolean
  isEnabled?: boolean
  isDefault?: boolean
}

export interface IAgentUpdateRequest {
  name?: string
  description?: string
  systemPrompt?: string
  model?: string | null
  toolProfile?: string[]
  memoryScopes?: string[]
  ragEnabled?: boolean
  isEnabled?: boolean
  isDefault?: boolean
}

export interface IAgentChatRequest {
  message: string
  agentKey?: string | null
  model?: string
  sessionId?: string | null
  attachmentIds?: string[]
}

export type RichBlockType = 'card' | 'table' | 'markdown' | 'chart' | 'sources'

export interface IRichBlock {
  type: RichBlockType
  title?: string | null
  data: Record<string, unknown>
}

export interface IChartPoint {
  x: string | number
  y: number
}

export interface IChartSeries {
  name: string
  points: IChartPoint[]
}

export interface IChartBlockData {
  chartType: 'line' | 'bar'
  xLabel?: string | null
  yLabel?: string | null
  series: IChartSeries[]
}

export interface ISourceItem {
  index: number
  url: string
  title?: string | null
  snippet?: string | null
  publishedAt?: string | null
}

export interface ISourcesBlockData {
  items: ISourceItem[]
}

export interface IAgentRunStep {
  id: string
  stepIndex: number
  stepType: string
  name?: string | null
  inputData?: Record<string, unknown> | null
  outputData?: Record<string, unknown> | null
  createdAt: string
}

export interface IAgentRunSummary {
  id: string
  sessionId?: string | null
  agentKey: string
  status: AgentRunStatus
  inputMessage: string
  outputMessage?: string | null
  createdAt: string
  completedAt?: string | null
}

export interface IAgentSessionSummary {
  id: string
  agentKey: string
  title?: string | null
  createdAt: string
  lastMessageAt: string
}

export interface IAgentSessionsListResponse {
  sessions: IAgentSessionSummary[]
  total: number
}

export interface IAgentSessionDetail extends IAgentSessionSummary {
  runs: IAgentRun[]
}

export interface IAgentRunsListResponse {
  runs: IAgentRunSummary[]
  total: number
}

export interface IAgentRun extends IAgentRunSummary {
  systemPrompt: string
  model: string
  promptTokens: number
  completionTokens: number
  totalTokens: number
  costUsd?: number | null
  blocks: IRichBlock[]
  steps: IAgentRunStep[]
}

export interface IAgentChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  runId?: string
  blocks?: IRichBlock[]
  attachments?: import('@/modules/workspace/types/attachments').IChatAttachment[]
  contextHints?: import('@/modules/workspace/types/contextHints').IComposerContextHint[]
}

export interface IAgentStreamStepEvent {
  type: AgentStepType
  stepIndex?: number
  tool?: string
  arguments?: Record<string, unknown>
  result?: Record<string, unknown>
  finishReason?: string
  runId?: string
  sessionId?: string
  agentKey?: string
  routingReason?: AgentRoutingReason
}

export interface IAgentStreamCompleteEvent {
  runId: string
  sessionId?: string
  message: string
  blocks?: IRichBlock[]
  promptTokens?: number
  completionTokens?: number
  totalTokens?: number
  costUsd?: number | null
  agentKey?: string
  routingReason?: AgentRoutingReason
}
