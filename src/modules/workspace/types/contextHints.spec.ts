import { describe, expect, it } from 'vitest'
import {
  buildContextDirectives,
  mergeMessageWithContextHints,
} from '@/modules/workspace/types/contextHints'
import type { IComposerContextHint } from '@/modules/workspace/types/contextHints'

const hint = (provider: IComposerContextHint['provider']): IComposerContextHint => ({
  id: `ctx-${provider}`,
  provider,
})

describe('buildContextDirectives', () => {
  it('returns nothing without hints', () => {
    expect(buildContextDirectives([])).toBe('')
  })

  it('emits a web search directive naming both web tools', () => {
    const directives = buildContextDirectives([hint('web')])
    expect(directives).toContain('web_search')
    expect(directives).toContain('web_fetch')
    expect(directives).toContain('cite the sources')
  })

  it('lists one line per hint under a single header', () => {
    const directives = buildContextDirectives([hint('github'), hint('web')])
    expect(directives.startsWith('[Context hints]')).toBe(true)
    expect(directives.split('\n')).toHaveLength(3)
  })
})

describe('mergeMessageWithContextHints', () => {
  it('prepends directives to the user message', () => {
    const merged = mergeMessageWithContextHints('  what is new in Vue?  ', [hint('web')])
    expect(merged.startsWith('[Context hints]')).toBe(true)
    expect(merged.endsWith('what is new in Vue?')).toBe(true)
  })

  it('returns the trimmed message when there are no hints', () => {
    expect(mergeMessageWithContextHints('  hello  ', [])).toBe('hello')
  })
})
