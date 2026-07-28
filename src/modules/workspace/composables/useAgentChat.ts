import { computed, ref } from 'vue'
import {
  copyRunToClipboard,
  getAgentRun,
  getAgentSession,
  streamAgentChat,
} from '@/modules/workspace/services/agentApiService'
import { mergeMessageWithContextHints } from '@/modules/workspace/types/contextHints'
import { getApiErrorMessage } from '@/shared/utils/apiError'
import type {
  AgentStepType,
  IAgentChatMessage,
  IAgentRun,
  IAgentRunStep,
  IAgentStreamStepEvent,
  IRichBlock,
} from '@/modules/workspace/types/agent'
import type { IChatAttachment } from '@/modules/workspace/types/attachments'
import type { IComposerContextHint } from '@/modules/workspace/types/contextHints'

function mapPersistedStep(step: IAgentRunStep): IAgentStreamStepEvent {
  return {
    type: step.stepType as AgentStepType,
    stepIndex: step.stepIndex,
    tool: step.name ?? undefined,
    arguments: step.inputData ?? undefined,
    result: step.outputData ?? undefined,
    runId: undefined,
  }
}

function runToMessages(run: IAgentRun): IAgentChatMessage[] {
  const messages: IAgentChatMessage[] = [
    {
      id: `user-${run.id}`,
      role: 'user',
      content: run.inputMessage,
      runId: run.id,
    },
  ]

  if (run.outputMessage) {
    messages.push({
      id: `assistant-${run.id}`,
      role: 'assistant',
      content: run.outputMessage,
      runId: run.id,
      blocks: run.blocks,
    })
  }

  return messages
}

export function useAgentChat(
  getSelectedModel?: () => string | undefined,
  getSelectedAgentKey?: () => string | undefined,
) {
  const messages = ref<IAgentChatMessage[]>([])
  const steps = ref<IAgentStreamStepEvent[]>([])
  const isStreaming = ref(false)
  const isLoadingRun = ref(false)
  const isLoading = computed(() => isStreaming.value || isLoadingRun.value)
  const error = ref<string | null>(null)
  const activeRunId = ref<string | null>(null)
  const activeRun = ref<IAgentRun | null>(null)
  const activeSessionId = ref<string | null>(null)
  const sessionAgentKey = ref<string | null>(null)

  const sendMessage = async (
    message: string,
    attachmentPayload?: IChatAttachment[],
    contextHintPayload?: IComposerContextHint[],
  ): Promise<string | undefined> => {
    const trimmed = message.trim()
    const files = attachmentPayload ?? []
    const hints = contextHintPayload ?? []
    if ((!trimmed && files.length === 0) || isLoading.value) return undefined

    isStreaming.value = true
    error.value = null
    steps.value = []
    activeRun.value = null

    const outboundMessage = mergeMessageWithContextHints(trimmed, hints)

    const userMessage: IAgentChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: trimmed,
      attachments: files.length ? files : undefined,
      contextHints: hints.length ? hints : undefined,
    }
    messages.value.push(userMessage)

    let assistantContent = ''
    let blocks: IRichBlock[] = []
    let runId: string | undefined

    const agentKey = sessionAgentKey.value ?? getSelectedAgentKey?.()

    try {
      await streamAgentChat(
        {
          message: outboundMessage || ' ',
          agentKey: activeSessionId.value ? undefined : agentKey,
          model: getSelectedModel?.(),
          sessionId: activeSessionId.value,
          attachmentIds: files.map((f) => f.id),
        },
        {
          onStep: (event) => {
            steps.value.push(event)
            if (event.runId) {
              runId = event.runId
              activeRunId.value = event.runId
            }
            if (event.sessionId) {
              activeSessionId.value = event.sessionId
            }
            if (event.agentKey) {
              sessionAgentKey.value = event.agentKey
            }
          },
          onComplete: (event) => {
            assistantContent = event.message
            blocks = event.blocks ?? []
            runId = event.runId
            activeRunId.value = event.runId
            if (event.sessionId) {
              activeSessionId.value = event.sessionId
            }
            if (event.agentKey) {
              sessionAgentKey.value = event.agentKey
            }
          },
          onError: (msg) => {
            error.value = msg
          },
        },
      )

      if (assistantContent) {
        messages.value.push({
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content: assistantContent,
          runId,
          blocks,
        })
      } else if (error.value) {
        messages.value.push({
          id: `assistant-error-${Date.now()}`,
          role: 'assistant',
          content: `**Error:** ${error.value}`,
        })
      } else {
        const fallback = 'Agent did not return a response'
        error.value = fallback
        messages.value.push({
          id: `assistant-error-${Date.now()}`,
          role: 'assistant',
          content: `**Error:** ${fallback}`,
        })
      }

      if (runId) {
        try {
          activeRun.value = await getAgentRun(runId)
        } catch {
          // Run metadata is optional for chat UX
        }
      }
    } catch (err) {
      error.value = getApiErrorMessage(err, 'Unknown error')
    } finally {
      isStreaming.value = false
    }

    return runId
  }

  const loadRun = async (runId: string) => {
    isLoadingRun.value = true
    error.value = null
    try {
      const run = await getAgentRun(runId)
      messages.value = runToMessages(run)
      steps.value = run.steps.map(mapPersistedStep)
      activeRunId.value = run.id
      activeRun.value = run
      activeSessionId.value = run.sessionId ?? null
    } catch (err) {
      error.value = getApiErrorMessage(err, 'Failed to load session')
      throw err
    } finally {
      isLoadingRun.value = false
    }
  }

  const loadSession = async (sessionId: string) => {
    isLoadingRun.value = true
    error.value = null
    try {
      const session = await getAgentSession(sessionId)
      messages.value = session.runs.flatMap(runToMessages)
      const lastRun = session.runs[session.runs.length - 1]
      steps.value = lastRun ? lastRun.steps.map(mapPersistedStep) : []
      activeRunId.value = lastRun?.id ?? null
      activeRun.value = lastRun ?? null
      activeSessionId.value = session.id
      sessionAgentKey.value = session.agentKey
    } catch (err) {
      error.value = getApiErrorMessage(err, 'Failed to load session')
      throw err
    } finally {
      isLoadingRun.value = false
    }
  }

  const copyActiveRun = async () => {
    if (!activeRunId.value) return
    await copyRunToClipboard(activeRunId.value)
  }

  const clearChat = () => {
    messages.value = []
    steps.value = []
    error.value = null
    activeRunId.value = null
    activeRun.value = null
    activeSessionId.value = null
    sessionAgentKey.value = null
  }

  return {
    messages,
    steps,
    isLoading,
    isStreaming,
    isLoadingRun,
    error,
    activeRunId,
    activeRun,
    activeSessionId,
    sessionAgentKey,
    sendMessage,
    loadRun,
    loadSession,
    copyActiveRun,
    clearChat,
  }
}
