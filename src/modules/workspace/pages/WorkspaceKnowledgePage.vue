<script setup lang="ts">
import { BookOpen, Eye, Trash2 } from 'lucide-vue-next'
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { toast } from 'vue-sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import ChatLayout from '@/layouts/ChatLayout.vue'
import { useKnowledgeBrowser } from '@/modules/workspace/composables/useKnowledgeBrowser'
import type { KnowledgeDocumentStatus } from '@/modules/workspace/types/knowledge'

const { t } = useI18n()

const newTitle = ref('')
const newContent = ref('')

const {
  documents,
  total,
  isLoading,
  isSaving,
  error,
  previewDocument,
  isPreviewLoading,
  loadDocuments,
  addDocument,
  removeDocument,
  openPreview,
  closePreview,
} = useKnowledgeBrowser()

onMounted(() => {
  void loadDocuments()
})

const handleAdd = async () => {
  const title = newTitle.value.trim()
  const content = newContent.value.trim()
  if (!title || !content) return
  try {
    await addDocument(title, content)
    newTitle.value = ''
    newContent.value = ''
    toast.success(t('workspace.knowledge.added'))
  } catch {
    toast.error(t('workspace.knowledge.addFailed'))
  }
}

const handleDelete = async (documentId: string) => {
  try {
    await removeDocument(documentId)
    toast.success(t('workspace.knowledge.deleted'))
  } catch {
    toast.error(t('workspace.knowledge.deleteFailed'))
  }
}

const statusVariant = (status: KnowledgeDocumentStatus) => {
  if (status === 'ready') return 'success'
  if (status === 'failed') return 'destructive'
  return 'secondary'
}

const formatDate = (iso: string) => new Date(iso).toLocaleString()
</script>

<template>
  <ChatLayout>
    <div class="flex min-h-0 flex-1 flex-col gap-4 overflow-hidden px-4 py-3 sm:px-6">
      <div class="flex shrink-0 items-center gap-2">
        <BookOpen class="size-5 text-muted-foreground" />
        <div>
          <h1 class="text-lg font-semibold">
            {{ t('workspace.knowledge.title') }}
          </h1>
          <p class="text-sm text-muted-foreground">
            {{ t('workspace.knowledge.subtitle') }}
          </p>
        </div>
      </div>

      <div class="shrink-0 space-y-2 rounded-xl border border-hairline bg-surface-raised p-4">
        <Label for="knowledge-title">{{ t('workspace.knowledge.add') }}</Label>
        <Input
          id="knowledge-title"
          v-model="newTitle"
          :placeholder="t('workspace.knowledge.titlePlaceholder')"
        />
        <Textarea
          v-model="newContent"
          :placeholder="t('workspace.knowledge.contentPlaceholder')"
          rows="4"
        />
        <div class="flex justify-end">
          <Button :disabled="isSaving || !newTitle.trim() || !newContent.trim()" @click="handleAdd">
            {{ t('workspace.knowledge.addAction') }}
          </Button>
        </div>
      </div>

      <p v-if="error" class="shrink-0 text-sm text-destructive">
        {{ error }}
      </p>

      <div class="min-h-0 flex-1 overflow-y-auto rounded-xl border border-hairline bg-surface-canvas">
        <p v-if="isLoading" class="p-4 text-sm text-muted-foreground">
          {{ t('workspace.knowledge.loading') }}
        </p>
        <p v-else-if="documents.length === 0" class="p-4 text-sm text-muted-foreground">
          {{ t('workspace.knowledge.empty') }}
        </p>
        <ul v-else class="divide-y divide-hairline">
          <li
            v-for="doc in documents"
            :key="doc.id"
            class="flex items-start justify-between gap-3 p-4"
          >
            <div class="min-w-0 flex-1 space-y-1">
              <p class="truncate text-sm font-medium">
                {{ doc.title }}
              </p>
              <div class="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <Badge :variant="statusVariant(doc.status)">
                  {{ t(`workspace.knowledge.statuses.${doc.status}`) }}
                </Badge>
                <span>{{ doc.sourceType }}</span>
                <span>{{ t('workspace.knowledge.chunkCount', { count: doc.chunkCount }) }}</span>
                <span>{{ formatDate(doc.createdAt) }}</span>
              </div>
              <p v-if="doc.status === 'failed' && doc.error" class="text-xs text-destructive">
                {{ doc.error }}
              </p>
            </div>
            <div class="flex shrink-0 gap-1">
              <Button
                variant="ghost"
                size="icon"
                :aria-label="t('workspace.knowledge.preview')"
                :disabled="doc.status !== 'ready'"
                @click="openPreview(doc.id)"
              >
                <Eye class="size-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                :aria-label="t('workspace.knowledge.delete')"
                @click="handleDelete(doc.id)"
              >
                <Trash2 class="size-4 text-destructive" />
              </Button>
            </div>
          </li>
        </ul>
      </div>

      <p class="shrink-0 text-xs text-muted-foreground">
        {{ t('workspace.knowledge.total', { count: total }) }}
      </p>
    </div>

    <Dialog :open="previewDocument !== null" @update:open="(open) => !open && closePreview()">
      <DialogContent class="max-w-2xl border-hairline bg-surface-raised">
        <DialogHeader>
          <DialogTitle class="truncate">
            {{ previewDocument?.title }}
          </DialogTitle>
        </DialogHeader>
        <div class="max-h-[60vh] space-y-3 overflow-y-auto">
          <p v-if="isPreviewLoading" class="text-sm text-muted-foreground">
            {{ t('workspace.knowledge.loading') }}
          </p>
          <div
            v-for="chunk in previewDocument?.chunks ?? []"
            :key="chunk.id"
            class="rounded-lg border border-hairline p-3"
          >
            <p class="mb-1 font-mono text-xs text-muted-foreground">
              {{ t('workspace.knowledge.chunkLabel', { index: chunk.chunkIndex + 1 }) }}
            </p>
            <p class="whitespace-pre-wrap text-sm">
              {{ chunk.content }}
            </p>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  </ChatLayout>
</template>
