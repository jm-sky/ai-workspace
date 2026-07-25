import { computed, onUnmounted, ref } from 'vue'
import {
  createKnowledgeDocument,
  deleteKnowledgeDocument,
  getKnowledgeDocument,
  listKnowledgeDocuments,
} from '@/modules/workspace/services/knowledgeApiService'
import { getApiErrorMessage } from '@/shared/utils/apiError'
import type {
  IKnowledgeDocument,
  IKnowledgeDocumentDetail,
} from '@/modules/workspace/types/knowledge'

const POLL_INTERVAL_MS = 3000

export function useKnowledgeBrowser() {
  const documents = ref<IKnowledgeDocument[]>([])
  const total = ref(0)
  const isLoading = ref(false)
  const isSaving = ref(false)
  const error = ref<string | null>(null)
  const previewDocument = ref<IKnowledgeDocumentDetail | null>(null)
  const isPreviewLoading = ref(false)

  let pollTimer: ReturnType<typeof setTimeout> | null = null

  const hasPending = computed(() => documents.value.some((doc) => doc.status === 'pending'))

  const stopPolling = () => {
    if (pollTimer) {
      clearTimeout(pollTimer)
      pollTimer = null
    }
  }

  const schedulePoll = () => {
    stopPolling()
    if (!hasPending.value) return
    pollTimer = setTimeout(() => {
      void loadDocuments({ silent: true })
    }, POLL_INTERVAL_MS)
  }

  const loadDocuments = async (options?: { silent?: boolean }) => {
    if (!options?.silent) {
      isLoading.value = true
    }
    error.value = null
    try {
      const response = await listKnowledgeDocuments({ limit: 100, offset: 0 })
      documents.value = response.documents
      total.value = response.total
      schedulePoll()
    } catch (err) {
      error.value = getApiErrorMessage(err, 'Failed to load documents')
    } finally {
      isLoading.value = false
    }
  }

  const addDocument = async (title: string, content: string) => {
    isSaving.value = true
    error.value = null
    try {
      await createKnowledgeDocument({ title, content })
      await loadDocuments()
    } catch (err) {
      error.value = getApiErrorMessage(err, 'Failed to add document')
      throw err
    } finally {
      isSaving.value = false
    }
  }

  const removeDocument = async (documentId: string) => {
    error.value = null
    try {
      await deleteKnowledgeDocument(documentId)
      documents.value = documents.value.filter((doc) => doc.id !== documentId)
      total.value = Math.max(0, total.value - 1)
      if (previewDocument.value?.id === documentId) {
        previewDocument.value = null
      }
    } catch (err) {
      error.value = getApiErrorMessage(err, 'Failed to delete document')
      throw err
    }
  }

  const openPreview = async (documentId: string) => {
    isPreviewLoading.value = true
    try {
      previewDocument.value = await getKnowledgeDocument(documentId)
    } catch (err) {
      error.value = getApiErrorMessage(err, 'Failed to load document')
    } finally {
      isPreviewLoading.value = false
    }
  }

  const closePreview = () => {
    previewDocument.value = null
  }

  onUnmounted(() => {
    stopPolling()
  })

  return {
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
  }
}
