import { describe, expect, it } from 'vitest'
import { buildChartRows, chartColorFor } from './chartBlock'
import type { IChartBlockData } from '@/modules/workspace/types/agent'

describe('buildChartRows', () => {
  it('merges series into rows keyed by x, preserving first-seen order', () => {
    const data: Pick<IChartBlockData, 'series'> = {
      series: [
        {
          name: '2026',
          points: [
            { x: 'Jan', y: 100 },
            { x: 'Feb', y: 120 },
          ],
        },
        {
          name: '2027',
          points: [
            { x: 'Feb', y: 90 },
            { x: 'Mar', y: 130 },
          ],
        },
      ],
    }

    const rows = buildChartRows(data)

    expect(rows.map((row) => row.x)).toEqual(['Jan', 'Feb', 'Mar'])
    expect(rows[0].values).toEqual([100, 0])
    expect(rows[1].values).toEqual([120, 90])
    expect(rows[2].values).toEqual([0, 130])
  })

  it('returns an empty array for a series with no points', () => {
    expect(buildChartRows({ series: [] })).toEqual([])
  })
})

describe('chartColorFor', () => {
  it('cycles through 5 chart colors', () => {
    expect(chartColorFor(0)).toBe('var(--chart-1)')
    expect(chartColorFor(4)).toBe('var(--chart-5)')
    expect(chartColorFor(5)).toBe('var(--chart-1)')
  })
})
