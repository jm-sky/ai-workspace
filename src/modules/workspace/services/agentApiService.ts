import { useAuthStore } from '@/modules/auth/store/useAuthStore'
import { apiClient } from '@/shared/services/apiClient'
import {
  CSRF_HEADER_NAME,
  ensureCsrfToken,
  getCsrfToken,
} from '@/shared/services/csrf'
import type {
  IAgentAdminListResponse,
  IAgentChatRequest,
  IAgentCreateRequest,
  IAgentDetail,
  IAgentListResponse,
  IAgentRun,
  IAgentRunsListResponse,
  IAgentSessionDetail,
  IAgentSessionsListResponse,
  IAgentStreamCompleteEvent,
  IAgentStreamStepEvent,
  IAgentUpdateRequest,
} from '@/modules/workspace/types/agent'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api'

export async function listAgents(): Promise<IAgentListResponse> {
  const response = await apiClient.get<IAgentListResponse>('/agent/agents')
  return response.data
}

export async function listAgentsManage(): Promise<IAgentAdminListResponse> {
  const response = await apiClient.get<IAgentAdminListResponse>('/agent/agents/manage')
  return response.data
}

export async function getAgentManage(agentId: string): Promise<IAgentDetail> {
  const response = await apiClient.get<IAgentDetail>(`/agent/agents/manage/${agentId}`)
  return response.data
}

export async function createAgent(body: IAgentCreateRequest): Promise<IAgentDetail> {
  const response = await apiClient.post<IAgentDetail>('/agent/agents', body)
  return response.data
}

export async function updateAgent(
  agentId: string,
  body: IAgentUpdateRequest,
): Promise<IAgentDetail> {
  const response = await apiClient.patch<IAgentDetail>(`/agent/agents/${agentId}`, body)
  return response.data
}

export async function setDefaultAgent(agentId: string): Promise<IAgentDetail> {
  const response = await apiClient.post<IAgentDetail>(
    `/agent/agents/${agentId}/set-default`,
  )
  return response.data
}

export async function streamAgentChat(
  request: IAgentChatRequest,
  handlers: {
    onStep?: (event: IAgentStreamStepEvent) => void
    onComplete?: (event: IAgentStreamCompleteEvent) => void
    onError?: (message: string) => void
  },
): Promise<void> {
  const token = useAuthStore().token
  let csrfToken = getCsrfToken()
  if (!csrfToken) {
    csrfToken = await ensureCsrfToken()
  }

  const response = await fetch(`${API_BASE}/agent/chat/stream`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(csrfToken ? { [CSRF_HEADER_NAME]: csrfToken } : {}),
    },
    body: JSON.stringify({
      message: request.message,
      agentKey: request.agentKey ?? undefined,
      model: request.model,
      sessionId: request.sessionId ?? undefined,
      attachmentIds: request.attachmentIds?.length
        ? request.attachmentIds
        : undefined,
    }),
  })

  if (!response.ok) {
    const text = await response.text()
    handlers.onError?.(text || `HTTP ${response.status}`)
    return
  }

  const reader = response.body?.getReader()
  if (!reader) {
    handlers.onError?.('No response stream')
    return
  }

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() ?? ''

    for (const part of parts) {
      const lines = part.split('\n')
      let eventType = 'message'
      let dataLine = ''

      for (const line of lines) {
        if (line.startsWith('event:')) {
          eventType = line.slice(6).trim()
        } else if (line.startsWith('data:')) {
          dataLine = line.slice(5).trim()
        }
      }

      if (!dataLine) continue

      try {
        const payload = JSON.parse(dataLine) as Record<string, unknown>
        if (eventType === 'step') {
          handlers.onStep?.(payload as unknown as IAgentStreamStepEvent)
        } else if (eventType === 'run_complete') {
          handlers.onComplete?.(payload as unknown as IAgentStreamCompleteEvent)
        } else if (eventType === 'error') {
          handlers.onError?.(String(payload.message ?? 'Agent error'))
        }
      } catch {
        handlers.onError?.('Failed to parse SSE payload')
      }
    }
  }
}

export async function listAgentRuns(params?: {
  limit?: number
  offset?: number
}): Promise<IAgentRunsListResponse> {
  const response = await apiClient.get<IAgentRunsListResponse>('/agent/runs', {
    params: {
      limit: params?.limit ?? 50,
      offset: params?.offset ?? 0,
    },
  })
  return response.data
}

export async function getAgentRun(runId: string): Promise<IAgentRun> {
  const response = await apiClient.get<IAgentRun>(`/agent/runs/${runId}`)
  return response.data
}

export async function listAgentSessions(params?: {
  limit?: number
  offset?: number
}): Promise<IAgentSessionsListResponse> {
  const response = await apiClient.get<IAgentSessionsListResponse>(
    '/agent/sessions',
    {
      params: {
        limit: params?.limit ?? 30,
        offset: params?.offset ?? 0,
      },
    },
  )
  return response.data
}

export async function getAgentSession(
  sessionId: string,
): Promise<IAgentSessionDetail> {
  const response = await apiClient.get<IAgentSessionDetail>(
    `/agent/sessions/${sessionId}`,
  )
  return response.data
}

export async function fetchAgentRun(runId: string): Promise<IAgentRun> {
  const token = useAuthStore().token
  const response = await fetch(`${API_BASE}/agent/runs/${runId}/export`, {
    credentials: 'include',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!response.ok) {
    throw new Error(`Failed to load run: ${response.status}`)
  }
  return response.json() as Promise<IAgentRun>
}

export async function copyRunToClipboard(runId: string): Promise<void> {
  const run = await fetchAgentRun(runId)
  await navigator.clipboard.writeText(JSON.stringify(run, null, 2))
}
