<script setup lang="ts">
import { Bot, Loader2, Plus, Star } from 'lucide-vue-next'
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { toast } from 'vue-sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useTenantStore } from '@/modules/tenants/store/useTenantStore'
import {
  createAgent,
  listAgentsManage,
  setDefaultAgent,
  updateAgent,
} from '@/modules/workspace/services/agentApiService'
import { getApiErrorMessage } from '@/shared/utils/apiError'
import type { IAgentDetail } from '@/modules/workspace/types/agent'

// Must stay in sync with TOOL_BUCKETS in backend agent/routers/agents.py.
const TOOL_BUCKETS = ['github', 'gmail', 'jira', 'gitlab', 'memory', 'rag', 'wiki', 'web'] as const

const { t } = useI18n()
const tenantStore = useTenantStore()

const canManage = computed(() => {
  const role = tenantStore.activeTenantRole
  return role === 'owner' || role === 'admin'
})

const agents = ref<IAgentDetail[]>([])
const isLoading = ref(false)
const isSaving = ref(false)
const selectedId = ref<string | null>(null)
const isCreating = ref(false)

const form = reactive({
  key: '',
  name: '',
  description: '',
  systemPrompt: '',
  model: '',
  toolProfile: [] as string[],
  ragEnabled: false,
  isEnabled: true,
  isDefault: false,
})

const selected = computed(() =>
  agents.value.find((a) => a.id === selectedId.value) ?? null,
)

const load = async () => {
  if (!canManage.value) return
  isLoading.value = true
  try {
    const response = await listAgentsManage()
    agents.value = response.agents
  } catch (err) {
    toast.error(getApiErrorMessage(err, t('settings.agents.loadError')))
  } finally {
    isLoading.value = false
  }
}

const fillForm = (agent: IAgentDetail) => {
  isCreating.value = false
  selectedId.value = agent.id
  form.key = agent.key
  form.name = agent.name
  form.description = agent.description
  form.systemPrompt = agent.systemPrompt
  form.model = agent.model ?? ''
  form.toolProfile = [...agent.toolProfile]
  form.ragEnabled = agent.ragEnabled
  form.isEnabled = agent.isEnabled
  form.isDefault = agent.isDefault
}

const startCreate = () => {
  isCreating.value = true
  selectedId.value = null
  form.key = ''
  form.name = ''
  form.description = ''
  form.systemPrompt = ''
  form.model = ''
  form.toolProfile = ['memory']
  form.ragEnabled = false
  form.isEnabled = true
  form.isDefault = false
}

const toggleBucket = (bucket: string, checked: boolean | 'indeterminate') => {
  const on = checked === true
  if (on && !form.toolProfile.includes(bucket)) {
    form.toolProfile.push(bucket)
  } else if (!on) {
    form.toolProfile = form.toolProfile.filter((b) => b !== bucket)
  }
}

const save = async () => {
  isSaving.value = true
  try {
    if (isCreating.value) {
      const created = await createAgent({
        key: form.key.trim(),
        name: form.name.trim(),
        description: form.description.trim(),
        systemPrompt: form.systemPrompt,
        model: form.model.trim() || null,
        toolProfile: form.toolProfile,
        ragEnabled: form.ragEnabled,
        isEnabled: form.isEnabled,
        isDefault: form.isDefault,
      })
      toast.success(t('settings.agents.created'))
      await load()
      fillForm(created)
    } else if (selectedId.value) {
      const updated = await updateAgent(selectedId.value, {
        name: form.name.trim(),
        description: form.description.trim(),
        systemPrompt: form.systemPrompt,
        model: form.model.trim() || null,
        toolProfile: form.toolProfile,
        ragEnabled: form.ragEnabled,
        isEnabled: form.isEnabled,
        isDefault: form.isDefault,
      })
      toast.success(t('settings.agents.saved'))
      await load()
      fillForm(updated)
    }
  } catch (err) {
    toast.error(getApiErrorMessage(err, t('settings.agents.saveError')))
  } finally {
    isSaving.value = false
  }
}

const makeDefault = async (agent: IAgentDetail) => {
  try {
    await setDefaultAgent(agent.id)
    toast.success(t('settings.agents.defaultSet'))
    await load()
    if (selectedId.value === agent.id) {
      const refreshed = agents.value.find((a) => a.id === agent.id)
      if (refreshed) fillForm(refreshed)
    }
  } catch (err) {
    toast.error(getApiErrorMessage(err, t('settings.agents.saveError')))
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div class="space-y-1">
        <h2 class="text-xl font-semibold">
          {{ t('settings.agents.title') }}
        </h2>
        <p class="text-sm text-muted-foreground">
          {{ t('settings.agents.description') }}
        </p>
      </div>
      <Button
        v-if="canManage"
        variant="outline"
        size="sm"
        @click="startCreate"
      >
        <Plus class="size-4" />
        {{ t('settings.agents.create') }}
      </Button>
    </div>

    <p
      v-if="!canManage"
      class="rounded-md border border-hairline bg-muted/40 px-3 py-2 text-sm text-muted-foreground"
    >
      {{ t('settings.agents.memberHint') }}
    </p>

    <div
      v-else-if="isLoading"
      class="flex items-center gap-2 text-sm text-muted-foreground"
    >
      <Loader2 class="size-4 animate-spin" />
      {{ t('settings.agents.loading') }}
    </div>

    <div
      v-else
      class="grid gap-6 lg:grid-cols-[minmax(0,14rem)_1fr]"
    >
      <ul class="space-y-1">
        <li
          v-for="agent in agents"
          :key="agent.id"
        >
          <button
            type="button"
            class="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors"
            :class="selectedId === agent.id && !isCreating
              ? 'bg-accent font-medium text-accent-foreground'
              : 'text-muted-foreground hover:bg-accent/50 hover:text-foreground'"
            @click="fillForm(agent)"
          >
            <Bot class="size-4 shrink-0" />
            <span class="min-w-0 flex-1 truncate">{{ agent.name }}</span>
            <Star
              v-if="agent.isDefault"
              class="size-3.5 shrink-0 text-amber-500"
            />
          </button>
        </li>
        <li
          v-if="agents.length === 0"
          class="px-3 py-2 text-sm text-muted-foreground"
        >
          {{ t('settings.agents.empty') }}
        </li>
      </ul>

      <div
        v-if="isCreating || selected"
        class="space-y-4 rounded-lg border border-hairline bg-surface-raised p-4"
      >
        <div class="flex flex-wrap items-center gap-2">
          <h3 class="text-base font-medium">
            {{ isCreating ? t('settings.agents.createTitle') : t('settings.agents.editTitle') }}
          </h3>
          <Badge
            v-if="form.isDefault"
            variant="secondary"
          >
            {{ t('settings.agents.defaultBadge') }}
          </Badge>
          <Badge
            v-if="!form.isEnabled"
            variant="outline"
          >
            {{ t('settings.agents.disabledBadge') }}
          </Badge>
        </div>

        <div
          v-if="isCreating"
          class="space-y-2"
        >
          <Label for="agent-key">{{ t('settings.agents.fields.key') }}</Label>
          <Input
            id="agent-key"
            v-model="form.key"
            placeholder="my-agent"
          />
        </div>
        <div
          v-else
          class="text-xs text-muted-foreground"
        >
          {{ t('settings.agents.fields.key') }}: <code>{{ form.key }}</code>
        </div>

        <div class="space-y-2">
          <Label for="agent-name">{{ t('settings.agents.fields.name') }}</Label>
          <Input
            id="agent-name"
            v-model="form.name"
          />
        </div>

        <div class="space-y-2">
          <Label for="agent-desc">{{ t('settings.agents.fields.description') }}</Label>
          <Textarea
            id="agent-desc"
            v-model="form.description"
            rows="2"
          />
        </div>

        <div class="space-y-2">
          <Label for="agent-prompt">{{ t('settings.agents.fields.systemPrompt') }}</Label>
          <Textarea
            id="agent-prompt"
            v-model="form.systemPrompt"
            rows="10"
            class="font-mono text-xs"
          />
        </div>

        <div class="space-y-2">
          <Label for="agent-model">{{ t('settings.agents.fields.model') }}</Label>
          <Input
            id="agent-model"
            v-model="form.model"
            :placeholder="t('settings.agents.fields.modelPlaceholder')"
          />
        </div>

        <div class="space-y-2">
          <Label>{{ t('settings.agents.fields.tools') }}</Label>
          <div class="flex flex-wrap gap-3">
            <label
              v-for="bucket in TOOL_BUCKETS"
              :key="bucket"
              class="flex items-center gap-2 text-sm"
            >
              <Checkbox
                :model-value="form.toolProfile.includes(bucket)"
                @update:model-value="toggleBucket(bucket, $event)"
              />
              {{ bucket }}
            </label>
          </div>
        </div>

        <div class="flex flex-wrap gap-4">
          <label class="flex items-center gap-2 text-sm">
            <Checkbox
              :model-value="form.ragEnabled"
              @update:model-value="form.ragEnabled = $event === true"
            />
            {{ t('settings.agents.fields.rag') }}
          </label>
          <label class="flex items-center gap-2 text-sm">
            <Checkbox
              :model-value="form.isEnabled"
              @update:model-value="form.isEnabled = $event === true"
            />
            {{ t('settings.agents.fields.enabled') }}
          </label>
          <label class="flex items-center gap-2 text-sm">
            <Checkbox
              :model-value="form.isDefault"
              @update:model-value="form.isDefault = $event === true"
            />
            {{ t('settings.agents.fields.default') }}
          </label>
        </div>

        <div class="flex flex-wrap gap-2">
          <Button
            :disabled="isSaving"
            @click="save"
          >
            <Loader2
              v-if="isSaving"
              class="size-4 animate-spin"
            />
            {{ t('settings.common.save') }}
          </Button>
          <Button
            v-if="selected && !selected.isDefault"
            variant="outline"
            :disabled="isSaving"
            @click="makeDefault(selected)"
          >
            <Star class="size-4" />
            {{ t('settings.agents.setDefault') }}
          </Button>
        </div>
      </div>

      <p
        v-else
        class="text-sm text-muted-foreground"
      >
        {{ t('settings.agents.selectHint') }}
      </p>
    </div>
  </div>
</template>
