<script setup lang="ts">
import { Send } from 'lucide-vue-next'
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import ChatAttachmentChip from '@/modules/workspace/components/ChatAttachmentChip.vue'
import ChatAttachmentPreview from '@/modules/workspace/components/ChatAttachmentPreview.vue'
import ChatComposerPlusMenu from '@/modules/workspace/components/ChatComposerPlusMenu.vue'
import ChatContextChip from '@/modules/workspace/components/ChatContextChip.vue'
import type { IChatAttachment } from '@/modules/workspace/types/attachments'
import type {
  ComposerContextProvider,
  IComposerContextHint,
} from '@/modules/workspace/types/contextHints'

const input = defineModel<string>({ required: true })

const {
  isLoading,
  isStreaming,
  canSubmit = true,
  attachments = [],
  contextHints = [],
  isUploading = false,
  accept = 'image/jpeg,image/png,image/webp,image/gif',
} = defineProps<{
  isLoading?: boolean
  isStreaming?: boolean
  canSubmit?: boolean
  attachments?: IChatAttachment[]
  contextHints?: IComposerContextHint[]
  isUploading?: boolean
  accept?: string
}>()

const emit = defineEmits<{
  submit: []
  pick: [files: FileList]
  removeAttachment: [id: string]
  addContext: [provider: ComposerContextProvider]
  removeContext: [id: string]
}>()

const { t } = useI18n()
const previewOpen = ref(false)
const previewItem = ref<IChatAttachment | null>(null)
const isDragging = ref(false)

const canSend = computed(
  () =>
    canSubmit
    && !isLoading
    && !isUploading
    && (input.value.trim().length > 0 || attachments.length > 0),
)

const hasChips = computed(
  () => attachments.length > 0 || contextHints.length > 0,
)

const handleSubmit = () => {
  if (!canSend.value) return
  emit('submit')
}

const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleSubmit()
  }
}

const openPreview = (item: IChatAttachment) => {
  previewItem.value = item
  previewOpen.value = true
}

const onPaste = (event: ClipboardEvent) => {
  const files = event.clipboardData?.files
  if (files?.length) {
    event.preventDefault()
    emit('pick', files)
  }
}

const onDrop = (event: DragEvent) => {
  isDragging.value = false
  const files = event.dataTransfer?.files
  if (files?.length) {
    event.preventDefault()
    emit('pick', files)
  }
}
</script>

<template>
  <div class="sticky bottom-0 shrink-0 bg-linear-to-t from-surface-canvas via-surface-canvas/95 to-transparent px-3 pb-4 pt-3 sm:px-4">
    <form
      class="shadow-composer mx-auto flex w-full max-w-3xl flex-col gap-2 rounded-3xl border border-hairline bg-surface-raised/90 p-2 backdrop-blur-md transition-[box-shadow,border-color] focus-within:border-ring/40"
      :class="isDragging ? 'border-ring/60' : ''"
      @submit.prevent="handleSubmit"
      @dragover.prevent="isDragging = true"
      @dragleave.prevent="isDragging = false"
      @drop.prevent="onDrop"
    >
      <div
        v-if="hasChips"
        class="flex flex-wrap gap-2 px-1 pt-1"
      >
        <ChatContextChip
          v-for="hint in contextHints"
          :key="hint.id"
          :hint="hint"
          @remove="emit('removeContext', hint.id)"
        />
        <ChatAttachmentChip
          v-for="item in attachments"
          :key="item.id"
          :attachment="item"
          @preview="openPreview(item)"
          @remove="emit('removeAttachment', item.id)"
        />
      </div>
      <div class="flex items-end gap-2">
        <ChatComposerPlusMenu
          :accept="accept"
          :disabled="isLoading || isUploading"
          @pick="emit('pick', $event)"
          @add-context="emit('addContext', $event)"
        />
        <Textarea
          id="chat-composer-input"
          v-model="input"
          :placeholder="t('workspace.chat.placeholder')"
          :disabled="isLoading"
          rows="1"
          class="min-h-9 rounded-full min-w-0 flex-1 resize-none border-0 bg-transparent px-2 py-1.5 shadow-none focus-visible:ring-0 dark:bg-transparent"
          :aria-label="t('workspace.chat.placeholder')"
          @keydown="handleKeydown"
          @paste="onPaste"
        />
        <Button
          type="submit"
          class="shrink-0 rounded-xl aspect-square p-2"
          :loading="isStreaming"
          :disabled="!canSend"
        >
          <Send class="size-4" />
          <span class="hidden sm:inline">{{ t('workspace.chat.send') }}</span>
        </Button>
      </div>
    </form>
    <ChatAttachmentPreview
      v-model:open="previewOpen"
      :attachment="previewItem"
    />
  </div>
</template>
