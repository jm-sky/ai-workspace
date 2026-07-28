<script setup lang="ts">
import {
  BookOpen,
  Brain,
  Check,
  Github,
  Gitlab,
  Globe,
  Loader2,
  Mail,
  Ticket,
  TriangleAlert,
  Wrench,
} from 'lucide-vue-next'
import { computed } from 'vue'
import type { Component } from 'vue'
import type { IAgentStreamStepEvent } from '@/modules/workspace/types/agent'

const props = defineProps<{
  steps: IAgentStreamStepEvent[]
}>()

type ActivityStatus = 'pending' | 'done' | 'error'

interface IToolActivity {
  id: string
  tool: string
  provider: string
  status: ActivityStatus
  detail: string
}

const PROVIDER_ICON: Record<string, Component> = {
  jira: Ticket,
  gitlab: Gitlab,
  github: Github,
  gmail: Mail,
  memory: Brain,
  rag: BookOpen,
  web: Globe,
}

const providerOf = (tool: string): string => {
  const prefix = tool.split('_')[0] ?? ''
  return prefix in PROVIDER_ICON ? prefix : 'tool'
}

const iconFor = (provider: string): Component => PROVIDER_ICON[provider] ?? Wrench

const countResult = (result?: Record<string, unknown>): string => {
  if (!result) return ''
  if ('error' in result) return String(result.error)
  let total = 0
  for (const value of Object.values(result)) {
    if (Array.isArray(value)) total += value.length
  }
  return total > 0 ? `${total}` : ''
}

const activities = computed<IToolActivity[]>(() => {
  const list: IToolActivity[] = []
  for (const step of props.steps) {
    if (step.type === 'tool_call' && step.tool) {
      list.push({
        id: `${step.tool}-${step.stepIndex ?? list.length}`,
        tool: step.tool,
        provider: providerOf(step.tool),
        status: 'pending',
        detail: '',
      })
    } else if (step.type === 'tool_result' && step.tool) {
      const pending = [...list].reverse().find(
        (activity) => activity.tool === step.tool && activity.status === 'pending',
      )
      if (pending) {
        const isError = !!step.result && 'error' in step.result
        pending.status = isError ? 'error' : 'done'
        pending.detail = countResult(step.result)
      }
    }
  }
  return list
})
</script>

<template>
  <ul
    v-if="activities.length"
    class="mr-auto flex w-full max-w-[85%] flex-col gap-1 rounded-xl border border-hairline bg-surface-raised/60 p-2"
  >
    <li
      v-for="activity in activities"
      :key="activity.id"
      class="flex items-center gap-2.5 px-1.5 py-1 text-sm"
    >
      <component
        :is="iconFor(activity.provider)"
        class="size-4 shrink-0 text-muted-foreground"
        aria-hidden="true"
      />
      <span class="font-mono text-xs text-foreground">{{ activity.tool }}</span>

      <span
        v-if="activity.detail && activity.status !== 'error'"
        class="rounded bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground"
      >
        {{ activity.detail }}
      </span>

      <span class="ml-auto flex items-center" aria-hidden="true">
        <Loader2
          v-if="activity.status === 'pending'"
          class="size-3.5 animate-spin text-muted-foreground"
        />
        <Check
          v-else-if="activity.status === 'done'"
          class="size-3.5 text-success"
        />
        <TriangleAlert
          v-else
          class="size-3.5 text-destructive"
        />
      </span>
    </li>
  </ul>
</template>
