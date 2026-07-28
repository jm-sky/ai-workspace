export type ComposerContextProvider = 'github' | 'gmail' | 'knowledge' | 'web'

export interface IComposerContextHint {
  id: string
  provider: ComposerContextProvider
}

/** Directives prepended to the outbound agent message (English for the model). */
export function buildContextDirectives(hints: IComposerContextHint[]): string {
  if (!hints.length) return ''
  const lines = hints.map((hint) => {
    switch (hint.provider) {
      case 'github':
        return '- Prefer GitHub tools for this request when relevant.'
      case 'gmail':
        return '- Prefer Gmail tools for this request when relevant.'
      case 'knowledge':
        return '- Prefer Knowledge / RAG (rag_search) for this request when relevant.'
      case 'web':
        return '- Search the web (web_search, then web_fetch) for this request, and cite the sources you use.'
      default:
        return ''
    }
  }).filter(Boolean)
  if (!lines.length) return ''
  return `[Context hints]\n${lines.join('\n')}`
}

export function mergeMessageWithContextHints(
  message: string,
  hints: IComposerContextHint[],
): string {
  const directives = buildContextDirectives(hints)
  const trimmed = message.trim()
  if (!directives) return trimmed
  if (!trimmed) return directives
  return `${directives}\n\n${trimmed}`
}
