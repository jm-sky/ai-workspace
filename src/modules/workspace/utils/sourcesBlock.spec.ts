import { describe, expect, it } from 'vitest'
import { readSourceItems, sourceDomain } from '@/modules/workspace/utils/sourcesBlock'

describe('sourceDomain', () => {
  it('strips scheme, path and www', () => {
    expect(sourceDomain('https://www.example.com/a/b?c=1')).toBe('example.com')
  })

  it('falls back to the raw value when the url does not parse', () => {
    expect(sourceDomain('not a url')).toBe('not a url')
  })
})

describe('readSourceItems', () => {
  it('returns an empty list when items are missing or not an array', () => {
    expect(readSourceItems({})).toEqual([])
    expect(readSourceItems({ items: 'nope' })).toEqual([])
  })

  it('drops entries without a usable url', () => {
    const items = readSourceItems({
      items: [{ index: 1, url: '  ' }, { index: 2 }, { index: 3, url: 'https://ok.example' }],
    })
    expect(items).toHaveLength(1)
    expect(items[0].url).toBe('https://ok.example')
  })

  it('de-duplicates by url and renumbers from one', () => {
    const items = readSourceItems({
      items: [
        { index: 7, url: 'https://a.example', title: 'A' },
        { index: 9, url: 'https://a.example', title: 'A again' },
        { index: 4, url: 'https://b.example', title: 'B' },
      ],
    })
    expect(items.map((item) => [item.index, item.title])).toEqual([
      [1, 'A'],
      [2, 'B'],
    ])
  })

  it('normalizes optional fields to null', () => {
    const [item] = readSourceItems({ items: [{ index: 1, url: 'https://a.example' }] })
    expect(item.title).toBeNull()
    expect(item.snippet).toBeNull()
    expect(item.publishedAt).toBeNull()
  })
})
