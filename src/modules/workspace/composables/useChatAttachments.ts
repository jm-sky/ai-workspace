import { computed, ref } from 'vue'
import {
  deleteChatAttachment,
  uploadChatAttachment,
} from '@/modules/workspace/services/attachmentApiService'
import { getApiErrorMessage } from '@/shared/utils/apiError'
import type { IChatAttachment } from '@/modules/workspace/types/attachments'

const IMAGE_MIME = new Set(['image/gif', 'image/jpeg', 'image/png', 'image/webp'])
const TEXT_EXT = new Set(['csv', 'json', 'md', 'txt', 'yaml', 'yml'])
const PDF_EXT = new Set(['pdf'])

export const ATTACHMENT_ACCEPT = [
  'image/jpeg',
  'image/png',
  'image/webp',
  'image/gif',
  'text/plain',
  'text/markdown',
  'text/csv',
  'application/json',
  'application/pdf',
  '.txt',
  '.md',
  '.json',
  '.csv',
  '.yaml',
  '.yml',
  '.pdf',
].join(',')

const MAX_PER_MESSAGE = 5
const MAX_FILE_BYTES = 10 * 1024 * 1024

const extensionOf = (name: string) => {
  const parts = name.toLowerCase().split('.')
  return parts.length > 1 ? parts.at(-1)! : ''
}

export const isImageFile = (file: File) => IMAGE_MIME.has(file.type)

export const isAllowedAttachmentFile = (file: File): boolean => {
  if (IMAGE_MIME.has(file.type)) return true
  if (file.type === 'application/pdf') return true
  if (
    file.type === 'text/plain'
    || file.type === 'text/markdown'
    || file.type === 'text/csv'
    || file.type === 'application/json'
    || file.type === 'application/yaml'
    || file.type === 'text/yaml'
  ) {
    return true
  }
  const ext = extensionOf(file.name)
  return TEXT_EXT.has(ext) || PDF_EXT.has(ext)
}

export function useChatAttachments() {
  const attachments = ref<IChatAttachment[]>([])
  const isUploading = ref(false)
  const error = ref<string | null>(null)
  const previewAttachment = ref<IChatAttachment | null>(null)

  const attachmentIds = computed(() => attachments.value.map((a) => a.id))
  const canAddMore = computed(() => attachments.value.length < MAX_PER_MESSAGE)
  const hasImages = computed(() => attachments.value.some((a) => a.kind === 'image'))

  const revokePreview = (item: IChatAttachment) => {
    if (item.previewUrl?.startsWith('blob:')) {
      URL.revokeObjectURL(item.previewUrl)
    }
  }

  const clearAttachments = (revoke = true) => {
    if (revoke) {
      for (const item of attachments.value) {
        revokePreview(item)
      }
    }
    attachments.value = []
    error.value = null
  }

  const takeAttachments = (): IChatAttachment[] => {
    const pending = [...attachments.value]
    attachments.value = []
    error.value = null
    return pending
  }

  const validateFile = (file: File, visionAllowed: boolean): string | null => {
    if (!isAllowedAttachmentFile(file)) {
      return 'unsupportedType'
    }
    if (isImageFile(file) && !visionAllowed) {
      return 'visionRequired'
    }
    if (file.size > MAX_FILE_BYTES) {
      return 'tooLarge'
    }
    if (!canAddMore.value) {
      return 'tooMany'
    }
    return null
  }

  const addFiles = async (
    files: FileList | File[],
    sessionId?: string | null,
    visionAllowed = true,
  ) => {
    const list = Array.from(files)
    if (list.length === 0) return

    isUploading.value = true
    error.value = null
    try {
      for (const file of list) {
        const code = validateFile(file, visionAllowed)
        if (code) {
          error.value = code
          continue
        }
        const uploaded = await uploadChatAttachment(file, sessionId)
        attachments.value.push({
          ...uploaded,
          previewUrl: uploaded.kind === 'image' ? URL.createObjectURL(file) : undefined,
        })
      }
    } catch (err) {
      error.value = getApiErrorMessage(err, 'uploadFailed')
    } finally {
      isUploading.value = false
    }
  }

  const removeAttachment = async (attachmentId: string) => {
    const item = attachments.value.find((a) => a.id === attachmentId)
    try {
      await deleteChatAttachment(attachmentId)
    } catch (err) {
      error.value = getApiErrorMessage(err, 'deleteFailed')
    }
    if (item) {
      revokePreview(item)
    }
    attachments.value = attachments.value.filter((a) => a.id !== attachmentId)
  }

  return {
    attachments,
    attachmentIds,
    isUploading,
    error,
    previewAttachment,
    canAddMore,
    hasImages,
    addFiles,
    removeAttachment,
    clearAttachments,
    takeAttachments,
    ATTACHMENT_ACCEPT,
    MAX_PER_MESSAGE,
    MAX_FILE_BYTES,
  }
}
