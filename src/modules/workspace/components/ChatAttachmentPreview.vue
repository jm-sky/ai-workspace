<script setup lang="ts">
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import type { IChatAttachment } from '@/modules/workspace/types/attachments'

const open = defineModel<boolean>('open', { required: true })

defineProps<{
  attachment: IChatAttachment | null
}>()
</script>

<template>
  <Dialog v-model:open="open">
    <DialogContent class="max-w-3xl border-hairline bg-surface-raised p-0">
      <DialogHeader class="px-4 pt-4">
        <DialogTitle class="truncate text-base">
          {{ attachment?.originalFilename }}
        </DialogTitle>
      </DialogHeader>
      <div class="flex max-h-[80vh] items-center justify-center p-4">
        <img
          v-if="attachment?.previewUrl"
          :src="attachment.previewUrl"
          :alt="attachment.originalFilename"
          class="max-h-[70vh] max-w-full rounded-lg object-contain"
        />
      </div>
    </DialogContent>
  </Dialog>
</template>
