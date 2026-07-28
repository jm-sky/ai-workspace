<script setup lang="ts">
import { useQuery } from '@tanstack/vue-query'
import { BookOpen, Github, Globe, Mail, Paperclip, Plus, Settings2 } from 'lucide-vue-next'
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { toast } from 'vue-sonner'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useAuth } from '@/modules/auth/composables/useAuth'
import {
  defaultGithubScopes,
  defaultGmailScopes,
  useIntegrationOAuth,
} from '@/modules/settings/composables/useIntegrationOAuth'
import { integrationService } from '@/modules/settings/services/integrationService'
import { WorkspaceRoutePath } from '@/modules/workspace/config/routes'
import type { IntegrationConnection } from '@/modules/settings/types/integration'
import type { ComposerContextProvider } from '@/modules/workspace/types/contextHints'

defineProps<{
  accept: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  pick: [files: FileList]
  addContext: [provider: ComposerContextProvider]
}>()

const { t } = useI18n()
const router = useRouter()
const { isAuthenticated } = useAuth()
const { connect, isPending: isConnecting } = useIntegrationOAuth()
const fileInput = ref<HTMLInputElement | null>(null)
const menuOpen = ref(false)

const { data: connections } = useQuery<IntegrationConnection[]>({
  queryKey: ['integration-connections'],
  queryFn: () => integrationService.listConnections(),
  enabled: isAuthenticated.value,
  staleTime: 60 * 1000,
})

const { data: setup } = useQuery({
  queryKey: ['integration-setup'],
  queryFn: () => integrationService.getSetup(),
  enabled: isAuthenticated.value,
  staleTime: 5 * 60 * 1000,
})

const connectedProviders = computed(() => {
  const set = new Set<string>()
  for (const connection of connections.value ?? []) {
    set.add(connection.provider)
  }
  return set
})

const githubEnabled = computed(
  () => setup.value?.providers.find((p) => p.id === 'github')?.enabled ?? false,
)
const gmailEnabled = computed(
  () => setup.value?.providers.find((p) => p.id === 'gmail')?.enabled ?? false,
)

const isGithubConnected = computed(() => connectedProviders.value.has('github'))
const isGmailConnected = computed(() => connectedProviders.value.has('gmail'))

const openFilePicker = () => {
  // Keep in the same user-gesture stack so the OS file dialog is allowed.
  fileInput.value?.click()
}

const onChange = (event: Event) => {
  const input = event.target as HTMLInputElement
  if (input.files?.length) {
    emit('pick', input.files)
    input.value = ''
  }
}

const useProvider = (provider: ComposerContextProvider) => {
  menuOpen.value = false
  emit('addContext', provider)
}

const connectProvider = async (provider: 'github' | 'gmail') => {
  menuOpen.value = false
  const enabled = provider === 'github' ? githubEnabled.value : gmailEnabled.value
  if (!enabled) {
    toast.error(t('workspace.composer.plus.providerDisabled'))
    await router.push(WorkspaceRoutePath.SettingsIntegrations)
    return
  }
  await connect({
    provider,
    scopes: provider === 'github' ? defaultGithubScopes() : defaultGmailScopes(),
    visibilityScope: 'user',
  })
}

const goIntegrations = async () => {
  menuOpen.value = false
  await router.push(WorkspaceRoutePath.SettingsIntegrations)
}
</script>

<template>
  <div>
    <input
      ref="fileInput"
      type="file"
      class="sr-only"
      :accept="accept"
      multiple
      :disabled="disabled"
      @change="onChange"
    />
    <DropdownMenu v-model:open="menuOpen">
      <DropdownMenuTrigger as-child>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          class="shrink-0 rounded-xl"
          :disabled="disabled || isConnecting"
          :title="t('workspace.composer.plus.open')"
          :aria-label="t('workspace.composer.plus.open')"
        >
          <Plus class="size-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="start"
        :side-offset="8"
        class="w-64"
      >
        <DropdownMenuItem @click="openFilePicker">
          <Paperclip class="size-4" />
          <span>{{ t('workspace.composer.plus.addFiles') }}</span>
        </DropdownMenuItem>

        <DropdownMenuSeparator />

        <DropdownMenuItem
          v-if="isGithubConnected"
          @click="useProvider('github')"
        >
          <Github class="size-4" />
          <span>{{ t('workspace.composer.plus.providers.github') }}</span>
        </DropdownMenuItem>
        <DropdownMenuItem
          v-else
          @click="connectProvider('github')"
        >
          <Github class="size-4" />
          <span>{{ t('workspace.composer.plus.connectGithub') }}</span>
        </DropdownMenuItem>

        <DropdownMenuItem
          v-if="isGmailConnected"
          @click="useProvider('gmail')"
        >
          <Mail class="size-4" />
          <span>{{ t('workspace.composer.plus.providers.gmail') }}</span>
        </DropdownMenuItem>
        <DropdownMenuItem
          v-else
          @click="connectProvider('gmail')"
        >
          <Mail class="size-4" />
          <span>{{ t('workspace.composer.plus.connectGmail') }}</span>
        </DropdownMenuItem>

        <DropdownMenuItem @click="useProvider('knowledge')">
          <BookOpen class="size-4" />
          <span>{{ t('workspace.composer.plus.providers.knowledge') }}</span>
        </DropdownMenuItem>

        <DropdownMenuItem @click="useProvider('web')">
          <Globe class="size-4" />
          <span>{{ t('workspace.composer.plus.providers.web') }}</span>
        </DropdownMenuItem>

        <DropdownMenuSeparator />

        <DropdownMenuItem @click="goIntegrations">
          <Settings2 class="size-4" />
          <span>{{ t('workspace.composer.plus.more') }}</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  </div>
</template>
