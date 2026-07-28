<script setup lang="ts">
import { BookOpen, Github, Globe, Mail, X } from 'lucide-vue-next'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Button } from '@/components/ui/button'
import type { IComposerContextHint } from '@/modules/workspace/types/contextHints'

const {
  hint,
  removable = true,
} = defineProps<{
  hint: IComposerContextHint
  removable?: boolean
}>()

const emit = defineEmits<{
  remove: []
}>()

const { t } = useI18n()

const icon = computed(() => {
  switch (hint.provider) {
    case 'github':
      return Github
    case 'gmail':
      return Mail
    case 'knowledge':
      return BookOpen
    case 'web':
      return Globe
    default:
      return BookOpen
  }
})

const label = computed(() => t(`workspace.composer.plus.providers.${hint.provider}`))
</script>

<template>
  <div
    class="relative flex items-center gap-2 rounded-xl border border-hairline bg-surface-canvas px-2.5 py-1.5"
    :class="removable ? 'pr-8' : ''"
  >
    <component
      :is="icon"
      class="size-3.5 shrink-0 text-muted-foreground"
    />
    <p class="truncate text-xs font-medium">
      {{ label }}
    </p>
    <Button
      v-if="removable"
      type="button"
      variant="ghost"
      size="icon"
      class="absolute right-0.5 top-0.5 size-7"
      :aria-label="t('workspace.composer.plus.removeHint')"
      @click="emit('remove')"
    >
      <X class="size-3.5" />
    </Button>
  </div>
</template>
