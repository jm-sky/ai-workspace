<script setup lang="ts">
import { ExternalLink } from 'lucide-vue-next'
import AgentChartBlock from '@/modules/workspace/components/AgentChartBlock.vue'
import AgentMarkdown from '@/modules/workspace/components/AgentMarkdown.vue'
import AgentSourcesBlock from '@/modules/workspace/components/AgentSourcesBlock.vue'
import type { IChartBlockData, IRichBlock } from '@/modules/workspace/types/agent'

const { blocks } = defineProps<{
  blocks: IRichBlock[]
}>()

const isTableBlock = (block: IRichBlock): boolean => block.type === 'table'
const isCardBlock = (block: IRichBlock): boolean => block.type === 'card'
const isMarkdownBlock = (block: IRichBlock): boolean => block.type === 'markdown'
const isChartBlock = (block: IRichBlock): boolean => block.type === 'chart'
const isSourcesBlock = (block: IRichBlock): boolean => block.type === 'sources'
const chartData = (block: IRichBlock): IChartBlockData => block.data as unknown as IChartBlockData

const tableRows = (block: IRichBlock): Record<string, unknown>[] => {
  const rows = block.data.rows
  return Array.isArray(rows) ? (rows as Record<string, unknown>[]) : []
}

const MONO_KEYS = new Set(['id', 'key', 'number', 'type'])
const STATE_KEYS = new Set(['state', 'status'])
const QUOTE_KEYS = new Set(['snippet', 'fragment'])

const isMono = (key: string): boolean => MONO_KEYS.has(key.toLowerCase())
const isState = (key: string): boolean => STATE_KEYS.has(key.toLowerCase())
const isQuoteKey = (key: string): boolean => QUOTE_KEYS.has(key.toLowerCase())

const cardFields = (block: IRichBlock): [string, unknown][] =>
  Object.entries(block.data).filter(
    ([key, value]) => value != null && value !== '' && !isQuoteKey(key),
  )

const cardQuote = (block: IRichBlock): string | null => {
  for (const key of QUOTE_KEYS) {
    const value = block.data[key]
    if (typeof value === 'string' && value.trim()) {
      return value
    }
  }
  return null
}

const pillClass = (value: unknown): string => {
  const v = String(value ?? '').toLowerCase()
  if (['active', 'in progress', 'open', 'opened', 'reopened', 'to do'].includes(v)) {
    return 'bg-success/15 text-success'
  }
  if (['done', 'merged', 'resolved'].includes(v)) {
    return 'bg-primary/15 text-primary'
  }
  if (['canceled', 'cancelled', 'closed'].includes(v)) {
    return 'bg-muted text-muted-foreground'
  }
  return 'bg-muted text-muted-foreground'
}
</script>

<template>
  <div class="mt-3 flex flex-col gap-4">
    <template v-for="(block, index) in blocks" :key="index">
      <div
        v-if="isCardBlock(block)"
        class="rounded-xl border border-hairline bg-surface-raised p-4"
      >
        <h3 v-if="block.title" class="mb-3 font-mono text-sm font-semibold tracking-tight">
          {{ block.title }}
        </h3>
        <dl class="grid gap-2 text-sm">
          <template
            v-for="([key, value]) in cardFields(block)"
            :key="key"
          >
            <div class="flex gap-2">
              <dt class="w-24 shrink-0 capitalize text-muted-foreground">
                {{ key }}
              </dt>
              <dd class="min-w-0 flex-1">
                <a
                  v-if="key === 'url' && typeof value === 'string'"
                  :href="value"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="inline-flex items-center gap-1 text-primary hover:underline"
                >
                  <span class="truncate">{{ value }}</span>
                  <ExternalLink class="size-3 shrink-0" />
                </a>
                <span
                  v-else-if="isState(String(key))"
                  :class="['inline-block rounded px-1.5 py-0.5 text-xs font-medium', pillClass(value)]"
                >
                  {{ value }}
                </span>
                <span v-else :class="isMono(String(key)) ? 'font-mono text-xs' : ''">
                  {{ value }}
                </span>
              </dd>
            </div>
          </template>
        </dl>
        <blockquote
          v-if="cardQuote(block)"
          class="mt-3 border-l-2 border-hairline pl-3 text-sm italic leading-relaxed text-muted-foreground"
        >
          {{ cardQuote(block) }}
        </blockquote>
      </div>

      <div
        v-else-if="isTableBlock(block)"
        class="overflow-hidden rounded-xl border border-hairline"
      >
        <h3
          v-if="block.title"
          class="border-b border-hairline bg-surface-raised px-3 py-2 font-mono text-sm font-semibold tracking-tight"
        >
          {{ block.title }}
        </h3>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-hairline bg-surface-raised/60 text-muted-foreground">
                <th
                  v-for="col in (block.data.columns as string[] | undefined) ?? []"
                  :key="col"
                  class="p-2 text-left font-medium capitalize"
                >
                  {{ col }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(row, rowIndex) in tableRows(block)"
                :key="rowIndex"
                class="border-b border-hairline transition-colors last:border-0 hover:bg-muted/40"
              >
                <td
                  v-for="col in (block.data.columns as string[] | undefined) ?? []"
                  :key="col"
                  class="p-2 align-top"
                >
                  <a
                    v-if="col === 'url' && typeof row[col] === 'string'"
                    :href="row[col] as string"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="inline-flex items-center gap-1 text-primary hover:underline"
                  >
                    <ExternalLink class="size-3.5" />
                  </a>
                  <span
                    v-else-if="isState(col)"
                    :class="['inline-block rounded px-1.5 py-0.5 text-xs font-medium', pillClass(row[col])]"
                  >
                    {{ row[col] }}
                  </span>
                  <span v-else :class="isMono(col) ? 'font-mono text-xs' : ''">
                    {{ row[col] }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <AgentMarkdown
        v-else-if="isMarkdownBlock(block) && typeof block.data.content === 'string'"
        :content="block.data.content"
      />

      <AgentChartBlock
        v-else-if="isChartBlock(block)"
        :title="block.title"
        :data="chartData(block)"
      />

      <AgentSourcesBlock
        v-else-if="isSourcesBlock(block)"
        :title="block.title"
        :data="block.data"
      />
    </template>
  </div>
</template>
