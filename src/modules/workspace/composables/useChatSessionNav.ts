import { inject, type InjectionKey, onMounted, provide, type Ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { toast } from 'vue-sonner'
import { useAgentSessions } from '@/modules/workspace/composables/useAgentSessions'
import { WorkspaceRoutePath } from '@/modules/workspace/routes'

export interface IChatSessionNavDeps {
  activeSessionId: Ref<string | null | undefined>
  loadSession: (sessionId: string) => Promise<void>
}

export interface IChatSessionNavContext {
  sessionsLoading: Ref<boolean>
  sessionsError: Ref<string | null>
  searchQuery: Ref<string>
  filteredSessions: ReturnType<typeof useAgentSessions>['filteredSessions']
  activeSessionId: Ref<string | null | undefined>
  selectSession: (sessionId: string) => Promise<void>
  newChat: () => Promise<void>
  refreshSessions: () => Promise<void>
  setSessionQuery: (sessionId?: string) => Promise<void>
}

const CHAT_SESSION_KEY: InjectionKey<IChatSessionNavContext> = Symbol('chatSession')

export function useChatSessionNav(deps: IChatSessionNavDeps): IChatSessionNavContext {
  const { t } = useI18n()
  const route = useRoute()
  const router = useRouter()

  const {
    isLoading: sessionsLoading,
    error: sessionsError,
    searchQuery,
    filteredSessions,
    loadSessions,
  } = useAgentSessions()

  const setSessionQuery = async (sessionId?: string) => {
    await router.replace({
      path: WorkspaceRoutePath.Chat,
      query: sessionId ? { session: sessionId } : {},
    })
  }

  const loadSessionFromRoute = async (sessionId: string) => {
    try {
      await deps.loadSession(sessionId)
    } catch {
      toast.error(t('workspace.sessions.loadError'))
    }
  }

  const selectSession = async (sessionId: string) => {
    await setSessionQuery(sessionId)
  }

  const newChat = async () => {
    await setSessionQuery()
  }

  const refreshSessions = async () => {
    await loadSessions()
  }

  onMounted(async () => {
    await loadSessions()
    const sessionId =
      typeof route.query.session === 'string' ? route.query.session : null
    if (sessionId) {
      await loadSessionFromRoute(sessionId)
    }
  })

  watch(
    () => route.query.session,
    async (sessionId) => {
      if (
        typeof sessionId === 'string' &&
        sessionId !== deps.activeSessionId.value
      ) {
        await loadSessionFromRoute(sessionId)
      }
    },
  )

  const context: IChatSessionNavContext = {
    sessionsLoading,
    sessionsError,
    searchQuery,
    filteredSessions,
    activeSessionId: deps.activeSessionId,
    selectSession,
    newChat,
    refreshSessions,
    setSessionQuery,
  }

  provide(CHAT_SESSION_KEY, context)

  return context
}

export function useChatSessionNavContext(): IChatSessionNavContext {
  const context = inject(CHAT_SESSION_KEY)
  if (!context) {
    throw new Error('useChatSessionNavContext must be used within a page that calls useChatSessionNav')
  }
  return context
}
