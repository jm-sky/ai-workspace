export const CHAT_ERROR_CODES = {
  BYOK_REQUIRED: 'byok_required',
  USAGE_LIMIT_EXCEEDED: 'usage_limit_exceeded',
  EMPTY_RESPONSE: 'empty_response',
  STREAM_FAILED: 'stream_failed',
} as const

export type ChatErrorCode = (typeof CHAT_ERROR_CODES)[keyof typeof CHAT_ERROR_CODES]
  | string

const ACTIONABLE_CHAT_ERROR_CODES = new Set<string>([
  CHAT_ERROR_CODES.BYOK_REQUIRED,
  CHAT_ERROR_CODES.USAGE_LIMIT_EXCEEDED,
])

export function isActionableChatErrorCode(code?: string): boolean {
  if (!code) return false
  return ACTIONABLE_CHAT_ERROR_CODES.has(code)
}
