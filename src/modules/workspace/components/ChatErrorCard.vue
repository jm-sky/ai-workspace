<script setup lang="ts">
import { TriangleAlert } from 'lucide-vue-next'
import { computed } from 'vue'
import Alert from '@/components/ui/alert/Alert.vue'
import AlertDescription from '@/components/ui/alert/AlertDescription.vue'
import AlertTitle from '@/components/ui/alert/AlertTitle.vue'
import ButtonLink from '@/components/ui/button-link/ButtonLink.vue'
import { BillingRoutePaths } from '@/modules/billing/routes'
import { useChatErrorPresentation } from '@/modules/workspace/composables/useChatErrorPresentation'

const props = defineProps<{
  message: string
  errorCode?: string
}>()

const { getErrorTitle, getErrorDescription, getErrorCtaLabel, showErrorCta } =
  useChatErrorPresentation()

const title = computed(() => getErrorTitle(props.errorCode))
const description = computed(() =>
  getErrorDescription(props.errorCode, props.message),
)
const ctaLabel = computed(() => getErrorCtaLabel(props.errorCode))
const showCta = computed(() => showErrorCta(props.errorCode) && ctaLabel.value)
</script>

<template>
  <Alert variant="destructive" class="w-full">
    <TriangleAlert />
    <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div class="min-w-0 flex-1 space-y-1">
        <AlertTitle>{{ title }}</AlertTitle>
        <AlertDescription>{{ description }}</AlertDescription>
      </div>
      <ButtonLink
        v-if="showCta"
        size="sm"
        variant="outline"
        class="shrink-0 border-destructive/40 bg-background hover:bg-destructive/10"
        :to="BillingRoutePaths.billing"
      >
        {{ ctaLabel }}
      </ButtonLink>
    </div>
  </Alert>
</template>
