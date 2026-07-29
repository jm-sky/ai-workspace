<script setup lang="ts">
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { Github, Link2, Mail, Trash2 } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { toast } from 'vue-sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useAuth } from '@/modules/auth/composables/useAuth'
import {
  defaultGithubScopes,
  defaultGmailScopes,
  useIntegrationOAuth,
  visibilityLabelKey,
} from '@/modules/settings/composables/useIntegrationOAuth'
import { integrationService } from '@/modules/settings/services/integrationService'
import { useHandleError } from '@/shared/composables/useHandleError'
import type {
  IntegrationConnection,
  IntegrationVisibilityScope,
} from '@/modules/settings/types/integration'

const { t } = useI18n()
const { isAuthenticated } = useAuth()
const { handleError } = useHandleError()
const queryClient = useQueryClient()
const { connect, isPending: isConnecting } = useIntegrationOAuth()

const selectedGithubScopes = ref<string[]>(defaultGithubScopes())
const selectedGmailScopes = ref<string[]>(defaultGmailScopes())
const visibilityScope = ref<IntegrationVisibilityScope>('user')
const selectedTeamId = ref<string | undefined>(undefined)

const { data: setup, isLoading: isSetupLoading, isError: isSetupError } = useQuery({
  queryKey: ['integration-setup'],
  queryFn: () => integrationService.getSetup(),
  enabled: isAuthenticated.value,
  staleTime: 5 * 60 * 1000,
})

const { data: connections, isLoading: isConnectionsLoading } = useQuery<IntegrationConnection[]>({
  queryKey: ['integration-connections'],
  queryFn: () => integrationService.listConnections(),
  enabled: isAuthenticated.value,
  staleTime: 60 * 1000,
})

const githubProvider = computed(() => setup.value?.providers.find(p => p.id === 'github'))
const gmailProvider = computed(() => setup.value?.providers.find(p => p.id === 'gmail'))
const githubEnabled = computed(() => githubProvider.value?.enabled ?? false)
const gmailEnabled = computed(() => gmailProvider.value?.enabled ?? false)
const canManageShared = computed(() => setup.value?.canManageShared ?? false)
const teams = computed(() => setup.value?.teams ?? [])

watch(visibilityScope, (scope) => {
  if (scope === 'team' && !selectedTeamId.value && teams.value.length > 0) {
    selectedTeamId.value = teams.value[0]?.id
  }
})

const deleteConnectionMutation = useMutation({
  mutationFn: (connectionId: string) => integrationService.deleteConnection(connectionId),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['integration-connections'] })
    toast.success(t('settings.integrations.connection.deleted'))
  },
  onError: (error: unknown) => {
    handleError(error)
  },
})

const toggleGithubScope = (scopeId: string, checked: boolean | 'indeterminate') => {
  const option = githubProvider.value?.scopes.find(s => s.id === scopeId)
  if (option?.required) {
    return
  }
  if (checked === true) {
    if (!selectedGithubScopes.value.includes(scopeId)) {
      selectedGithubScopes.value = [...selectedGithubScopes.value, scopeId]
    }
  }
  else {
    selectedGithubScopes.value = selectedGithubScopes.value.filter(id => id !== scopeId)
  }
}

const handleConnectGithub = async () => {
  if (!githubEnabled.value) {
    return
  }
  await connect({
    provider: 'github',
    scopes: selectedGithubScopes.value,
    visibilityScope: visibilityScope.value,
    teamId: visibilityScope.value === 'team' ? selectedTeamId.value : null,
  })
}

const handleConnectGmail = async () => {
  if (!gmailEnabled.value) {
    return
  }
  await connect({
    provider: 'gmail',
    scopes: selectedGmailScopes.value,
    visibilityScope: visibilityScope.value,
    teamId: visibilityScope.value === 'team' ? selectedTeamId.value : null,
  })
}

const handleDelete = async (connection: IntegrationConnection) => {
  const label = getProviderLabel(connection.provider)
  if (confirm(t('settings.integrations.connection.confirm_delete', { provider: label }))) {
    await deleteConnectionMutation.mutateAsync(connection.id)
  }
}

const getProviderLabel = (provider: string): string => {
  const labels: Record<string, string> = {
    github: t('settings.integrations.providers.github'),
    gmail: t('settings.integrations.providers.gmail'),
    jira: 'Jira',
    gitlab: 'GitLab',
  }
  return labels[provider] ?? provider
}

const getConnectionSubtitle = (connection: IntegrationConnection): string => {
  const meta = connection.providerMetadata
  if (meta?.email) {
    return String(meta.email)
  }
  if (meta?.login) {
    return String(meta.login)
  }
  if (connection.scopes) {
    return connection.scopes
  }
  return t('settings.integrations.connection.linked')
}

const visibilityOptions = computed(() => {
  const options: IntegrationVisibilityScope[] = ['user']
  if (canManageShared.value) {
    options.push('team', 'tenant')
  }
  return options
})

const isLoading = computed(() => isSetupLoading.value || isConnectionsLoading.value)
const hasConnections = computed(() => (connections.value?.length ?? 0) > 0)
</script>

<template>
  <Card>
    <CardHeader>
      <div class="flex items-center gap-2">
        <Link2 :size="20" />
        <CardTitle>{{ t('settings.integrations.title') }}</CardTitle>
      </div>
      <CardDescription>{{ t('settings.integrations.description') }}</CardDescription>
    </CardHeader>
    <CardContent class="space-y-6">
      <div v-if="!isAuthenticated" class="text-sm text-muted-foreground py-2">
        {{ t('settings.integrations.login_required') }}
      </div>

      <div v-else-if="isSetupError" class="text-sm text-muted-foreground py-2">
        {{ t('settings.integrations.tenant_required') }}
      </div>

      <div v-else-if="isLoading" class="space-y-2">
        <div class="h-4 w-3/4 bg-muted rounded animate-pulse" />
        <div class="h-4 w-1/2 bg-muted rounded animate-pulse" />
      </div>

      <template v-else>
        <div
          v-if="githubProvider"
          class="space-y-4 rounded-lg border p-4"
        >
          <div class="flex items-center gap-2">
            <Github class="size-5" />
            <h3 class="font-medium text-sm">
              {{ t('settings.integrations.providers.github') }}
            </h3>
          </div>

          <p
            v-if="!githubEnabled"
            class="text-sm text-muted-foreground"
          >
            {{ t('settings.integrations.github_not_configured') }}
          </p>

          <template v-else>
            <p
              v-if="githubProvider.kind === 'github_app'"
              class="text-xs text-muted-foreground"
            >
              {{ t('settings.integrations.github_app_permissions_hint') }}
            </p>

            <div class="space-y-2">
              <Label>{{ t('settings.integrations.scopes.title') }}</Label>
              <div
                v-for="scope in githubProvider.scopes"
                :key="scope.id"
                class="flex items-start gap-2"
              >
                <Checkbox
                  :id="`scope-${scope.id}`"
                  :model-value="selectedGithubScopes.includes(scope.id)"
                  :disabled="scope.required"
                  @update:model-value="toggleGithubScope(scope.id, $event)"
                />
                <div class="grid gap-1">
                  <Label
                    :for="`scope-${scope.id}`"
                    class="font-normal"
                  >
                    {{ t(scope.labelKey, scope.id) }}
                  </Label>
                  <p class="text-xs text-muted-foreground">
                    {{ t(scope.descriptionKey, '') }}
                  </p>
                </div>
              </div>
            </div>

            <div class="grid gap-2 sm:grid-cols-2">
              <div class="space-y-2">
                <Label>{{ t('settings.integrations.visibility.title') }}</Label>
                <Select v-model="visibilityScope">
                  <SelectTrigger>
                    <SelectValue :placeholder="t('settings.integrations.visibility.title')" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem
                      v-for="option in visibilityOptions"
                      :key="option"
                      :value="option"
                    >
                      {{ t(visibilityLabelKey(option)) }}
                    </SelectItem>
                  </SelectContent>
                </Select>
                <p class="text-xs text-muted-foreground">
                  {{ t(`settings.integrations.visibility.${visibilityScope}_hint`) }}
                </p>
              </div>

              <div
                v-if="visibilityScope === 'team'"
                class="space-y-2"
              >
                <Label>{{ t('settings.integrations.visibility.team_select') }}</Label>
                <Select v-model="selectedTeamId">
                  <SelectTrigger>
                    <SelectValue :placeholder="t('settings.integrations.visibility.team_select')" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem
                      v-for="team in teams"
                      :key="team.id"
                      :value="team.id"
                    >
                      {{ team.name }}
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <Button
              type="button"
              :disabled="isConnecting || selectedGithubScopes.length === 0"
              @click="handleConnectGithub"
            >
              <Github class="size-4" />
              {{ isConnecting
                ? t('settings.integrations.connect.redirecting')
                : t('settings.integrations.connect.github') }}
            </Button>
          </template>
        </div>

        <div
          v-if="gmailProvider"
          class="space-y-4 rounded-lg border p-4"
        >
          <div class="flex items-center gap-2">
            <Mail class="size-5" />
            <h3 class="font-medium text-sm">
              {{ t('settings.integrations.providers.gmail') }}
            </h3>
          </div>

          <p
            v-if="!gmailEnabled"
            class="text-sm text-muted-foreground"
          >
            {{ t('settings.integrations.gmail_not_configured') }}
          </p>

          <template v-else>
            <div class="space-y-2">
              <Label>{{ t('settings.integrations.scopes.title') }}</Label>
              <div
                v-for="scope in gmailProvider.scopes"
                :key="scope.id"
                class="flex items-start gap-2"
              >
                <Checkbox
                  :id="`gmail-scope-${scope.id}`"
                  :model-value="selectedGmailScopes.includes(scope.id)"
                  :disabled="scope.required"
                />
                <div class="grid gap-1">
                  <Label
                    :for="`gmail-scope-${scope.id}`"
                    class="font-normal"
                  >
                    {{ t(scope.labelKey, scope.id) }}
                  </Label>
                  <p class="text-xs text-muted-foreground">
                    {{ t(scope.descriptionKey, '') }}
                  </p>
                </div>
              </div>
            </div>

            <div class="grid gap-2 sm:grid-cols-2">
              <div class="space-y-2">
                <Label>{{ t('settings.integrations.visibility.title') }}</Label>
                <Select v-model="visibilityScope">
                  <SelectTrigger>
                    <SelectValue :placeholder="t('settings.integrations.visibility.title')" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem
                      v-for="option in visibilityOptions"
                      :key="option"
                      :value="option"
                    >
                      {{ t(visibilityLabelKey(option)) }}
                    </SelectItem>
                  </SelectContent>
                </Select>
                <p class="text-xs text-muted-foreground">
                  {{ t(`settings.integrations.visibility.${visibilityScope}_hint`) }}
                </p>
              </div>

              <div
                v-if="visibilityScope === 'team'"
                class="space-y-2"
              >
                <Label>{{ t('settings.integrations.visibility.team_select') }}</Label>
                <Select v-model="selectedTeamId">
                  <SelectTrigger>
                    <SelectValue :placeholder="t('settings.integrations.visibility.team_select')" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem
                      v-for="team in teams"
                      :key="team.id"
                      :value="team.id"
                    >
                      {{ team.name }}
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <Button
              type="button"
              :disabled="isConnecting || selectedGmailScopes.length === 0"
              @click="handleConnectGmail"
            >
              <Mail class="size-4" />
              {{ isConnecting
                ? t('settings.integrations.connect.redirecting_gmail')
                : t('settings.integrations.connect.gmail') }}
            </Button>
          </template>
        </div>

        <div class="space-y-3">
          <h3 class="text-sm font-medium">
            {{ t('settings.integrations.connections_title') }}
          </h3>

          <p
            v-if="!hasConnections"
            class="text-sm text-muted-foreground"
          >
            {{ t('settings.integrations.no_connections') }}
          </p>

          <div
            v-for="connection in connections"
            :key="connection.id"
            class="flex items-center justify-between gap-3 rounded-lg bg-muted/30 p-3"
          >
            <div class="min-w-0 flex-1 space-y-1">
              <p class="text-sm font-medium">
                {{ getProviderLabel(connection.provider) }}
                <span class="text-muted-foreground font-normal">
                  · {{ t(visibilityLabelKey(connection.visibilityScope)) }}
                </span>
              </p>
              <p class="truncate text-xs text-muted-foreground">
                {{ getConnectionSubtitle(connection) }}
              </p>
              <p
                v-if="connection.teamName"
                class="text-xs text-muted-foreground"
              >
                {{ connection.teamName }}
              </p>
            </div>
            <Button
              v-if="connection.canManage"
              variant="ghost"
              size="sm"
              :disabled="deleteConnectionMutation.isPending.value"
              @click="handleDelete(connection)"
            >
              <Trash2 class="size-4" />
            </Button>
          </div>
        </div>
      </template>
    </CardContent>
  </Card>
</template>
