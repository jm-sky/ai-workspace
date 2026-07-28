<script setup lang="ts">
import { Loader2 } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { toast } from 'vue-sonner'
import ChatLayout from '@/layouts/ChatLayout.vue'
import AgentAuditSheet from '@/modules/workspace/components/AgentAuditSheet.vue'
import AgentMarkdown from '@/modules/workspace/components/AgentMarkdown.vue'
import AgentRichBlocks from '@/modules/workspace/components/AgentRichBlocks.vue'
import ChatComposer from '@/modules/workspace/components/ChatComposer.vue'
import ChatContextChip from '@/modules/workspace/components/ChatContextChip.vue'
import ChatThinkingIndicator from '@/modules/workspace/components/ChatThinkingIndicator.vue'
import ChatToolbar from '@/modules/workspace/components/ChatToolbar.vue'
import ChatToolSteps from '@/modules/workspace/components/ChatToolSteps.vue'
import { useAgentChat } from '@/modules/workspace/composables/useAgentChat'
import { useAgentSessions } from '@/modules/workspace/composables/useAgentSessions'
import { useChatAttachments } from '@/modules/workspace/composables/useChatAttachments'
import { useComposerContextHints } from '@/modules/workspace/composables/useComposerContextHints'
import { useWorkspaceModels } from '@/modules/workspace/composables/useWorkspaceModels'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const input = ref('')
const auditOpen = ref(false)
const selectedAgentKey = ref('')

const { getSelectedModelId, hasValidModel, selectedModel } = useWorkspaceModels()
const { error: sessionsError, loadSessions } = useAgentSessions()
const {
  attachments,
  isUploading,
  error: attachmentError,
  hasImages,
  addFiles,
  removeAttachment,
  takeAttachments,
  ATTACHMENT_ACCEPT,
} = useChatAttachments()

const {
  contextHints,
  addContextHint,
  removeContextHint,
  takeContextHints,
} = useComposerContextHints()

const visionAllowed = computed(() => selectedModel.value?.supports_vision ?? false)

const {
  messages,
  steps,
  isLoading,
  isStreaming,
  isLoadingRun,
  activeRunId,
  activeRun,
  activeSessionId,
  sessionAgentKey,
  error,
  sendMessage,
  loadSession,
  copyActiveRun,
  clearChat,
} = useAgentChat(getSelectedModelId, () => selectedAgentKey.value || undefined)

watch(sessionAgentKey, (key) => {
  if (key) selectedAgentKey.value = key
})

const agentLocked = computed(
  () => Boolean(activeSessionId.value) || messages.value.length > 0,
)

const setSessionQuery = async (sessionId?: string) => {
  await router.replace({
    path: route.path,
    query: sessionId ? { session: sessionId } : {},
  })
}

const syncSessionFromRoute = async (sessionId: string | null) => {
  if (sessionId) {
    if (sessionId === activeSessionId.value) return
    try {
      await loadSession(sessionId)
    } catch {
      toast.error(t('workspace.sessions.loadError'))
    }
    return
  }

  if (activeSessionId.value || messages.value.length > 0) {
    clearChat()
  }
}

watch(
  () => route.query.session,
  async (sessionId) => {
    const id = typeof sessionId === 'string' ? sessionId : null
    await syncSessionFromRoute(id)
  },
  { immediate: true },
)

watch(attachmentError, (code) => {
  if (!code) return
  if (code === 'visionRequired') {
    toast.error(t('workspace.attachments.visionRequired'))
    return
  }
  const key = `workspace.attachments.errors.${code}`
  const translated = t(key)
  toast.error(translated === key ? code : translated)
})

const handlePick = async (files: FileList) => {
  await addFiles(files, activeSessionId.value, visionAllowed.value)
}

const handleSubmit = async () => {
  const text = input.value.trim()
  if ((!text && attachments.value.length === 0) || !hasValidModel.value) return
  if (hasImages.value && !visionAllowed.value) {
    toast.error(t('workspace.attachments.visionRequired'))
    return
  }
  const pending = takeAttachments()
  const pendingHints = takeContextHints()
  input.value = ''
  await sendMessage(text, pending, pendingHints)
  await loadSessions()
  if (activeSessionId.value) {
    await setSessionQuery(activeSessionId.value)
  }
}

const handleCopyRun = async () => {
  try {
    await copyActiveRun()
    toast.success(t('workspace.audit.copied'))
  } catch {
    toast.error(t('workspace.audit.copyFailed'))
  }
}
</script>

<template>
  <ChatLayout>
    <template #header-center>
      <ChatToolbar
        v-model:agent-key="selectedAgentKey"
        :active-run="activeRun"
        :step-count="steps.length"
        :audit-open="auditOpen"
        :agent-locked="agentLocked"
        @open-audit="auditOpen = true"
      />
    </template>

    <div class="flex min-h-0 flex-1 flex-col">
      <div class="flex min-h-0 flex-1 flex-col overflow-hidden">
        <div
          v-if="sessionsError || error || isLoadingRun"
          class="mx-auto flex w-full max-w-3xl shrink-0 flex-col gap-2 px-3 py-2 sm:px-4"
        >
          <p
            v-if="sessionsError"
            class="shrink-0 text-sm text-destructive"
          >
            {{ sessionsError }}
          </p>

          <p
            v-if="error"
            class="shrink-0 text-sm text-destructive"
          >
            {{ error }}
          </p>

          <div
            v-if="isLoadingRun"
            class="flex items-center gap-2 text-sm text-muted-foreground"
          >
            <Loader2 class="size-4 animate-spin" />
            {{ t('workspace.chat.loadingSession') }}
          </div>
        </div>

        <div class="min-h-0 flex-1 overflow-y-auto">
          <div class="mx-auto flex w-full max-w-3xl flex-col gap-6 px-3 pb-4 pt-3 sm:px-4">
            <div
              v-if="messages.length === 0 && !isLoadingRun"
              class="flex flex-1 flex-col items-center justify-center gap-2 py-16 text-center"
            >
              <h1 class="text-2xl font-semibold tracking-tight text-foreground">
                {{ t('workspace.chat.welcomeTitle') }}
              </h1>
              <p class="max-w-md text-sm text-muted-foreground">
                {{ t('workspace.chat.empty') }}
              </p>
            </div>

            <div
              v-for="msg in messages"
              :key="msg.id"
              :class="['w-full', msg.role === 'user' ? 'flex justify-end' : '']"
            >
              <div
                :class="msg.role === 'user'
                  ? 'max-w-[85%] rounded-2xl border border-hairline bg-surface-user px-4 py-2.5 text-foreground shadow-soft'
                  : 'w-full'"
              >
                <div
                  v-if="msg.contextHints?.length || msg.attachments?.length"
                  class="mb-2 flex flex-wrap gap-2"
                >
                  <ChatContextChip
                    v-for="hint in msg.contextHints ?? []"
                    :key="hint.id"
                    :hint="hint"
                    :removable="false"
                  />
                  <template
                    v-for="att in msg.attachments"
                    :key="att.id"
                  >
                    <img
                      v-if="att.kind === 'image' && att.previewUrl"
                      :src="att.previewUrl"
                      :alt="att.originalFilename"
                      class="size-16 rounded-lg object-cover"
                    />
                    <span
                      v-else
                      class="rounded-lg border border-hairline bg-muted px-2 py-1 text-xs"
                    >
                      {{ att.originalFilename }}
                    </span>
                  </template>
                </div>
                <AgentMarkdown
                  v-if="msg.content.trim()"
                  :content="msg.content"
                />
                <AgentRichBlocks
                  v-if="msg.blocks?.length"
                  :blocks="msg.blocks"
                />
              </div>
            </div>

            <ChatToolSteps
              v-if="isStreaming && steps.length"
              :steps="steps"
            />

            <ChatThinkingIndicator
              v-if="isStreaming"
              :steps="steps"
            />
          </div>
        </div>
      </div>

      <ChatComposer
        v-model="input"
        :is-loading="isLoading"
        :is-streaming="isStreaming"
        :can-submit="hasValidModel && !isLoading"
        :attachments="attachments"
        :context-hints="contextHints"
        :is-uploading="isUploading"
        :accept="ATTACHMENT_ACCEPT"
        @submit="handleSubmit"
        @pick="handlePick"
        @remove-attachment="removeAttachment"
        @add-context="addContextHint"
        @remove-context="removeContextHint"
      />

      <AgentAuditSheet
        v-model:open="auditOpen"
        :steps="steps"
        :run-id="activeRunId"
        :active-run="activeRun"
        :is-streaming="isStreaming"
        @copy-run="handleCopyRun"
      />
    </div>
  </ChatLayout>
</template>
