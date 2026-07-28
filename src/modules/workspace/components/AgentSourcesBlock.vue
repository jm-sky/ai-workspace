<script setup lang="ts">
import { ExternalLink, Globe } from 'lucide-vue-next'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { readSourceItems, sourceDomain } from '@/modules/workspace/utils/sourcesBlock'

const { title = null, data } = defineProps<{
  title?: string | null
  data: Record<string, unknown>
}>()

const { t } = useI18n()

const items = computed(() => readSourceItems(data))
</script>

<template>
  <section
    v-if="items.length"
    class="rounded-xl border border-hairline bg-surface-raised p-4"
  >
    <h3 class="mb-3 flex items-center gap-1.5 text-sm font-semibold tracking-tight">
      <Globe class="size-3.5 text-muted-foreground" />
      {{ title ?? t('workspace.blocks.sources.title') }}
    </h3>
    <ol class="flex flex-col gap-2">
      <li v-for="item in items" :key="item.url" class="flex gap-2 text-sm">
        <span class="mt-0.5 shrink-0 font-mono text-xs text-muted-foreground">
          [{{ item.index }}]
        </span>
        <div class="min-w-0 flex-1">
          <a
            :href="item.url"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex max-w-full items-center gap-1 text-primary hover:underline"
          >
            <span class="truncate">{{ item.title || item.url }}</span>
            <ExternalLink class="size-3 shrink-0" />
          </a>
          <p class="text-xs text-muted-foreground">
            {{ sourceDomain(item.url) }}
            <template v-if="item.publishedAt">
              · {{ item.publishedAt }}
            </template>
          </p>
        </div>
      </li>
    </ol>
  </section>
</template>
