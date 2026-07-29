<script setup lang="ts">
import { ChevronRight } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import type { IWikiPage } from '@/modules/workspace/types/wiki'

defineProps<{
  pages: IWikiPage[]
  selectedIds: Set<string>
  selectedPageId?: string | null
  isLoading: boolean
  allFilteredSelected: boolean
}>()

const emit = defineEmits<{
  selectPage: [id: string]
  toggleSelect: [id: string]
  selectAll: []
  clearSelection: []
}>()

const { t } = useI18n()

const formatDate = (iso: string) => new Date(iso).toLocaleString()
</script>

<template>
  <div class="size-full overflow-y-auto rounded-xl border border-hairline bg-surface-canvas">
    <p
      v-if="isLoading"
      class="p-4 text-sm text-muted-foreground"
    >
      {{ t('workspace.wiki.loading') }}
    </p>
    <p
      v-else-if="pages.length === 0"
      class="p-4 text-sm text-muted-foreground"
    >
      {{ t('workspace.wiki.empty') }}
    </p>
    <template v-else>
      <div class="flex items-center gap-2 border-b border-hairline px-3 py-2">
        <Checkbox
          :model-value="allFilteredSelected"
          @update:model-value="allFilteredSelected ? emit('clearSelection') : emit('selectAll')"
        />
        <span class="text-xs text-muted-foreground">
          {{ t('workspace.wiki.selectAll') }}
        </span>
      </div>
      <ul class="divide-y divide-hairline">
        <li
          v-for="page in pages"
          :key="page.id"
          class="flex cursor-pointer items-start gap-2 p-3 transition-colors hover:bg-muted/50"
          :class="{ 'bg-muted/30': selectedPageId === page.id }"
        >
          <Checkbox
            :model-value="selectedIds.has(page.id)"
            class="mt-0.5 shrink-0"
            @update:model-value="emit('toggleSelect', page.id)"
            @click.stop
          />
          <div
            class="min-w-0 flex-1"
            @click="emit('selectPage', page.id)"
          >
            <p class="truncate text-sm font-medium">
              {{ page.title }}
            </p>
            <div class="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Badge
                variant="outline"
                class="text-[10px]"
              >
                {{ page.folder }}
              </Badge>
              <Badge
                v-if="page.status === 'deprecated'"
                variant="secondary"
                class="text-[10px]"
              >
                {{ t('workspace.wiki.statusDeprecated') }}
              </Badge>
              <span>{{ formatDate(page.updatedAt) }}</span>
            </div>
          </div>
          <ChevronRight class="mt-1 size-3.5 shrink-0 text-muted-foreground" />
        </li>
      </ul>
    </template>
  </div>
</template>
