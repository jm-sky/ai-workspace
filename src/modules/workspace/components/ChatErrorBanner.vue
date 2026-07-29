<script setup lang="ts">
import { TriangleAlert, X } from 'lucide-vue-next'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import Alert from '@/components/ui/alert/Alert.vue'
import AlertDescription from '@/components/ui/alert/AlertDescription.vue'
import AlertTitle from '@/components/ui/alert/AlertTitle.vue'
import { Button } from '@/components/ui/button'
import ButtonLink from '@/components/ui/button-link/ButtonLink.vue'
import { BillingRoutePaths } from '@/modules/billing/routes'
import { useChatErrorPresentation } from '@/modules/workspace/composables/useChatErrorPresentation'
import type { IAgentStreamError } from '@/modules/workspace/types/agent'

const props = defineProps<{
  error: IAgentStreamError
}>()

const emit = defineEmits<{
  dismiss: []
}>()

const { t } = useI18n()
const { getErrorTitle, getErrorDescription, getErrorCtaLabel } =
  useChatErrorPresentation()

const title = computed(() => getErrorTitle(props.error.code))
const description = computed(() =>
  getErrorDescription(props.error.code, props.error.message),
)
const ctaLabel = computed(() => getErrorCtaLabel(props.error.code))
</script>

<template>
  <Alert variant="destructive" class="w-full">
    <TriangleAlert />
    <div class="flex flex-1 flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <div class="min-w-0 flex-1 space-y-1">
        <AlertTitle>{{ title }}</AlertTitle>
        <AlertDescription>{{ description }}</AlertDescription>
      </div>
      <div class="flex shrink-0 items-center gap-2">
        <ButtonLink
          v-if="ctaLabel"
          size="sm"
          variant="outline"
          class="border-destructive/40 bg-background hover:bg-destructive/10"
          :to="BillingRoutePaths.billing"
        >
          {{ ctaLabel }}
        </ButtonLink>
        <Button
          size="sm"
          variant="ghost"
          class="text-destructive hover:bg-destructive/10 hover:text-destructive"
          :aria-label="t('workspace.chat.errors.dismiss')"
          @click="emit('dismiss')"
        >
          <X class="size-4" />
        </Button>
      </div>
    </div>
  </Alert>
</template>
