<script setup lang="ts">
import { ScrollText } from 'lucide-vue-next'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import AgentPicker from '@/modules/workspace/components/AgentPicker.vue'
import WorkspaceModelSelector from '@/modules/workspace/components/WorkspaceModelSelector.vue'
import type { IAgentRun } from '@/modules/workspace/types/agent'

const agentKey = defineModel<string>('agentKey', { required: true })

const {
  activeRun,
  stepCount,
  auditOpen,
  agentLocked = false,
} = defineProps<{
  activeRun?: IAgentRun | null
  stepCount?: number
  auditOpen?: boolean
  agentLocked?: boolean
}>()

const emit = defineEmits<{
  openAudit: []
}>()

const { t } = useI18n()

const auditDisabled = computed(() => !activeRun && (stepCount ?? 0) === 0)
</script>

<template>
  <div class="flex min-w-0 flex-nowrap items-center justify-center gap-1.5 sm:gap-2">
    <AgentPicker
      v-model="agentKey"
      :locked="agentLocked"
    />

    <div class="min-w-0 w-[9.5rem] sm:w-[13rem]">
      <WorkspaceModelSelector />
    </div>

    <Tooltip>
      <TooltipTrigger as-child>
        <Button
          variant="outline"
          size="icon"
          class="relative size-8 shrink-0"
          :disabled="auditDisabled"
          :class="auditOpen ? 'bg-accent' : ''"
          :aria-label="t('workspace.audit.open')"
          @click="emit('openAudit')"
        >
          <ScrollText class="size-4" />
          <Badge
            v-if="(stepCount ?? 0) > 0"
            variant="secondary"
            class="absolute -right-1 -top-1 flex size-4 items-center justify-center p-0 text-[10px]"
          >
            {{ stepCount }}
          </Badge>
        </Button>
      </TooltipTrigger>
      <TooltipContent>
        {{ t('workspace.audit.openTooltip') }}
      </TooltipContent>
    </Tooltip>
  </div>
</template>
