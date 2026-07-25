<script setup lang="ts">
import { VisAxis, VisGroupedBar, VisLine, VisXYContainer } from '@unovis/vue'
import { computed } from 'vue'
import { ChartContainer } from '@/components/ui/chart'
import { buildChartRows, chartColorFor } from '@/modules/workspace/utils/chartBlock'
import type { ChartConfig } from '@/components/ui/chart'
import type { IChartBlockData } from '@/modules/workspace/types/agent'
import type { IChartRow } from '@/modules/workspace/utils/chartBlock'

const { title = null, data } = defineProps<{
  title?: string | null
  data: IChartBlockData
}>()

const rows = computed(() => buildChartRows(data))

const config = computed<ChartConfig>(() =>
  Object.fromEntries(data.series.map((series, index) => [`s${index}`, { label: series.name }])),
)

const colorFor = chartColorFor

const xTickFormat = (index: number): string => String(rows.value[index]?.x ?? '')

const seriesIndexes = computed<number[]>(() => data.series.map((_series, index) => index))

const yAccessor = (seriesIndex: number) => (row: IChartRow): number => row.values[seriesIndex] ?? 0

// VisGroupedBar groups bars side-by-side only when given array y/color accessors
// on a single instance — sibling <VisGroupedBar> components would overlap instead.
const barYAccessors = computed(() => seriesIndexes.value.map((i) => yAccessor(i)))
const barColors = computed(() => seriesIndexes.value.map((i) => colorFor(i)))
</script>

<template>
  <div class="rounded-xl border border-hairline bg-surface-raised p-4">
    <h3 v-if="title" class="mb-3 font-mono text-sm font-semibold tracking-tight">
      {{ title }}
    </h3>
    <ChartContainer :config="config" class="h-64">
      <VisXYContainer :data="rows">
        <template v-if="data.chartType === 'bar'">
          <VisGroupedBar
            :x="(_row: IChartRow, i: number) => i"
            :y="barYAccessors"
            :color="barColors"
          />
        </template>
        <template v-else>
          <VisLine
            v-for="seriesIndex in seriesIndexes"
            :key="seriesIndex"
            :x="(_row: IChartRow, i: number) => i"
            :y="yAccessor(seriesIndex)"
            :color="colorFor(seriesIndex)"
          />
        </template>
        <VisAxis type="x" :tick-format="xTickFormat" :label="data.xLabel ?? undefined" />
        <VisAxis type="y" :label="data.yLabel ?? undefined" />
      </VisXYContainer>
    </ChartContainer>
  </div>
</template>
