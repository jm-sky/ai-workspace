<script setup lang="ts">
import { AlertTriangle, Link2, Maximize2, Trash2 } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import type { IWikiPageDetail } from '@/modules/workspace/types/wiki'

const props = withDefaults(defineProps<{
  page: IWikiPageDetail
  showExpand?: boolean
}>(), {
  showExpand: false,
})

const emit = defineEmits<{
  deprecate: [id: string]
  delete: [id: string]
  expand: []
  navigateLink: [pageId: string, folder?: string | null]
}>()

const { t } = useI18n()

const statusVariant = (status: string) => {
  if (status === 'active') return 'success'
  return 'secondary'
}
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto">
    <div class="flex items-start justify-between gap-2">
      <div class="min-w-0">
        <h2 class="text-sm font-semibold">
          {{ props.page.title }}
        </h2>
        <div class="flex flex-wrap gap-1.5 text-xs text-muted-foreground">
          <Badge variant="outline">
            {{ props.page.folder }}
          </Badge>
          <Badge :variant="statusVariant(props.page.status)">
            {{ props.page.status }}
          </Badge>
          <TooltipProvider v-if="props.page.immutable">
            <Tooltip>
              <TooltipTrigger as-child>
                <span class="cursor-default">🔒</span>
              </TooltipTrigger>
              <TooltipContent>{{ t('workspace.wiki.help.immutable') }}</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      </div>
      <div class="flex shrink-0 gap-1">
        <TooltipProvider v-if="props.showExpand">
          <Tooltip>
            <TooltipTrigger as-child>
              <Button
                variant="ghost"
                size="icon"
                :aria-label="t('workspace.wiki.expandDetail')"
                @click="emit('expand')"
              >
                <Maximize2 class="size-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>{{ t('workspace.wiki.expandDetail') }}</TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <TooltipProvider v-if="!props.page.immutable && props.page.status === 'active'">
          <Tooltip>
            <TooltipTrigger as-child>
              <Button
                variant="ghost"
                size="icon"
                :aria-label="t('workspace.wiki.deprecate')"
                @click="emit('deprecate', props.page.id)"
              >
                <AlertTriangle class="size-4 text-amber-500" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>{{ t('workspace.wiki.help.deprecate') }}</TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <TooltipProvider v-if="!props.page.immutable">
          <Tooltip>
            <TooltipTrigger as-child>
              <Button
                variant="ghost"
                size="icon"
                :aria-label="t('workspace.wiki.delete')"
                @click="emit('delete', props.page.id)"
              >
                <Trash2 class="size-4 text-destructive" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>{{ t('workspace.wiki.help.delete') }}</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
    </div>

    <div class="whitespace-pre-wrap rounded-lg border border-hairline bg-surface-canvas p-3 text-sm">
      {{ props.page.bodyMd }}
    </div>

    <div v-if="props.page.outgoingLinks.length > 0">
      <h3 class="mb-1 flex items-center gap-1 text-xs font-medium text-muted-foreground">
        <Link2 class="size-3" />
        {{ t('workspace.wiki.outgoingLinks') }}
      </h3>
      <ul class="space-y-0.5">
        <li
          v-for="link in props.page.outgoingLinks"
          :key="link.id"
          class="text-xs"
        >
          <button
            v-if="link.toPageId"
            type="button"
            class="text-left text-primary underline-offset-2 hover:underline"
            @click="emit('navigateLink', link.toPageId, link.toFolder)"
          >
            [[{{ link.toSlug }}]]
            <span
              v-if="link.toTitle && link.toTitle !== link.toSlug"
              class="text-muted-foreground"
            > — {{ link.toTitle }}</span>
          </button>
          <span
            v-else
            class="text-primary"
          >
            [[{{ link.toSlug }}]]
          </span>
          <Badge
            v-if="link.toFolder"
            variant="outline"
            class="ml-1 text-[10px]"
          >
            {{ link.toFolder }}
          </Badge>
          <span
            v-if="!link.toPageId"
            class="text-destructive"
          >(dangling)</span>
        </li>
      </ul>
    </div>

    <div v-if="props.page.incomingLinks.length > 0">
      <h3 class="mb-1 flex items-center gap-1 text-xs font-medium text-muted-foreground">
        <Link2 class="size-3" />
        {{ t('workspace.wiki.incomingLinks') }}
      </h3>
      <ul class="space-y-0.5">
        <li
          v-for="link in props.page.incomingLinks"
          :key="link.id"
          class="text-xs"
        >
          <button
            type="button"
            class="text-left text-primary underline-offset-2 hover:underline"
            @click="emit('navigateLink', link.fromPageId, link.fromFolder)"
          >
            [[{{ link.fromSlug || link.fromPageId }}]]
            <span
              v-if="link.fromTitle"
              class="text-muted-foreground"
            > — {{ link.fromTitle }}</span>
          </button>
          <Badge
            v-if="link.fromFolder"
            variant="outline"
            class="ml-1 text-[10px]"
          >
            {{ link.fromFolder }}
          </Badge>
        </li>
      </ul>
    </div>
  </div>
</template>
