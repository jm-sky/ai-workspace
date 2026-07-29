<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useSubscription } from '../composables/useSubscription'

const { t } = useI18n()
const { limits, isLoadingLimits } = useSubscription()

const usedUsd = computed(() => limits.value?.workspaceUsedUsd ?? 0)
const capUsd = computed(() => limits.value?.workspaceMonthlyIncludedUsd ?? 0)
const progress = computed(() => {
  if (!capUsd.value || capUsd.value <= 0) return 0
  return Math.min(100, (usedUsd.value / capUsd.value) * 100)
})
const showUsage = computed(() => limits.value?.workspaceUsedUsd != null)
</script>

<template>
  <Card v-if="showUsage">
    <CardHeader>
      <CardTitle>{{ t('billing.workspaceUsage.title') }}</CardTitle>
      <CardDescription>{{ t('billing.workspaceUsage.description') }}</CardDescription>
    </CardHeader>
    <CardContent class="space-y-4">
      <div v-if="isLoadingLimits" class="text-sm text-muted-foreground">
        {{ t('common.loading') }}
      </div>
      <template v-else>
        <div class="flex justify-between text-sm">
          <span>{{ t('billing.workspaceUsage.used') }}</span>
          <span>${{ usedUsd.toFixed(4) }} / ${{ capUsd.toFixed(2) }}</span>
        </div>
        <div class="h-2 w-full overflow-hidden rounded-full bg-muted">
          <div
            class="h-full bg-primary transition-all"
            :style="{ width: `${progress}%` }"
          />
        </div>
        <p
          v-if="limits?.webSearchCap != null"
          class="text-xs text-muted-foreground"
        >
          {{ t('billing.workspaceUsage.webSearch', {
            used: limits?.webSearchUsed ?? 0,
            cap: limits?.webSearchCap,
          }) }}
        </p>
      </template>
    </CardContent>
  </Card>
</template>
