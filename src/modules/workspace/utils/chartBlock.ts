import type { IChartBlockData } from '@/modules/workspace/types/agent'

export interface IChartRow {
  x: string | number
  values: number[]
}

export const buildChartRows = (data: Pick<IChartBlockData, 'series'>): IChartRow[] => {
  const xValues: (string | number)[] = []
  const seen = new Set<string | number>()
  for (const series of data.series) {
    for (const point of series.points) {
      if (!seen.has(point.x)) {
        seen.add(point.x)
        xValues.push(point.x)
      }
    }
  }
  return xValues.map((x) => ({
    x,
    values: data.series.map((series) => series.points.find((p) => p.x === x)?.y ?? 0),
  }))
}

export const chartColorFor = (index: number): string => `var(--chart-${(index % 5) + 1})`
