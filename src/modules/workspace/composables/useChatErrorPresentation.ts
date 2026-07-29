import { useI18n } from 'vue-i18n'
import { isActionableChatErrorCode } from '@/modules/workspace/types/chatErrors'

function knownDescriptionKey(errorCode?: string): string | null {
  if (errorCode === 'byok_required') return 'workspace.chat.errors.byok.description'
  if (errorCode === 'usage_limit_exceeded') return 'workspace.chat.errors.usageLimit.description'
  if (errorCode === 'empty_response') return 'workspace.chat.errors.emptyResponse'
  if (errorCode === 'stream_failed') return 'workspace.chat.errors.streamFailed'
  return null
}

function knownTitleKey(errorCode?: string): string {
  if (errorCode === 'byok_required') return 'workspace.chat.errors.byok.title'
  if (errorCode === 'usage_limit_exceeded') return 'workspace.chat.errors.usageLimit.title'
  if (errorCode === 'empty_response') return 'workspace.chat.errors.emptyResponseTitle'
  if (errorCode === 'stream_failed') return 'workspace.chat.errors.streamFailedTitle'
  return 'workspace.chat.errors.genericTitle'
}

function knownCtaKey(errorCode?: string): string | null {
  if (errorCode === 'byok_required') return 'workspace.chat.errors.byok.cta'
  if (errorCode === 'usage_limit_exceeded') return 'workspace.chat.errors.usageLimit.cta'
  return null
}

export function useChatErrorPresentation() {
  const { t, te } = useI18n()

  const getErrorTitle = (errorCode?: string) => t(knownTitleKey(errorCode))

  const getErrorDescription = (errorCode: string | undefined, message: string) => {
    const key = knownDescriptionKey(errorCode)
    if (key && te(key)) return t(key)
    if (message.trim()) return message
    return t('workspace.chat.errors.genericDescription')
  }

  const getErrorCtaLabel = (errorCode?: string) => {
    const key = knownCtaKey(errorCode)
    return key ? t(key) : null
  }

  const showErrorCta = (errorCode?: string) => isActionableChatErrorCode(errorCode)

  return {
    getErrorTitle,
    getErrorDescription,
    getErrorCtaLabel,
    showErrorCta,
    isActionableChatErrorCode,
  }
}
