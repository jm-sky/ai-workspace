import type { ISourceItem, ISourcesBlockData } from '@/modules/workspace/types/agent'

/** Host shown under each source, without the noise of `www.` or the scheme. */
export const sourceDomain = (url: string): string => {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

/**
 * Read a `sources` block defensively.
 *
 * The backend already de-duplicates and renumbers, but a persisted run may carry
 * an older payload, so anything without a usable `url` is dropped and indices are
 * recomputed rather than trusted.
 */
export const readSourceItems = (data: Record<string, unknown>): ISourceItem[] => {
  const items = (data as Partial<ISourcesBlockData>).items
  if (!Array.isArray(items)) return []

  const seen = new Set<string>()
  const result: ISourceItem[] = []

  for (const item of items) {
    const url = typeof item?.url === 'string' ? item.url.trim() : ''
    if (!url || seen.has(url)) continue
    seen.add(url)
    result.push({
      index: result.length + 1,
      url,
      title: item.title ?? null,
      snippet: item.snippet ?? null,
      publishedAt: item.publishedAt ?? null,
    })
  }

  return result
}
