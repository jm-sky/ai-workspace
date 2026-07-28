<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { listAgents } from '@/modules/workspace/services/agentApiService'
import type { IAgentSummary } from '@/modules/workspace/types/agent'

const selectedKey = defineModel<string>({ required: true })

const { locked = false } = defineProps<{
  locked?: boolean
}>()

const { t } = useI18n()
const agents = ref<IAgentSummary[]>([])
const isLoading = ref(false)
const loadError = ref<string | null>(null)

const load = async () => {
  isLoading.value = true
  loadError.value = null
  try {
    const response = await listAgents()
    agents.value = response.agents
    if (!selectedKey.value) {
      const defaultAgent = response.agents.find((a) => a.isDefault) ?? response.agents[0]
      if (defaultAgent) {
        selectedKey.value = defaultAgent.key
      }
    }
  } catch {
    loadError.value = t('workspace.agent.loadError')
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  void load()
})

watch(selectedKey, (key) => {
  if (!key && agents.value.length) {
    const defaultAgent = agents.value.find((a) => a.isDefault) ?? agents.value[0]
    if (defaultAgent) selectedKey.value = defaultAgent.key
  }
})
</script>

<template>
  <div class="min-w-0 shrink-0">
    <Select
      v-model="selectedKey"
      :disabled="locked || isLoading || agents.length === 0"
    >
      <SelectTrigger
        size="sm"
        class="h-8 w-[9.5rem] max-w-full cursor-pointer sm:w-[13rem]"
        :aria-label="t('workspace.agent.selectLabel')"
      >
        <SelectValue :placeholder="t('workspace.agent.selectPlaceholder')" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem
          v-for="agent in agents"
          :key="agent.key"
          :value="agent.key"
        >
          {{ agent.name }}
        </SelectItem>
      </SelectContent>
    </Select>
    <p
      v-if="loadError"
      class="mt-1 text-xs text-destructive"
    >
      {{ loadError }}
    </p>
  </div>
</template>
