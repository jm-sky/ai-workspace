<script setup lang="ts">
import { computed } from 'vue'
import WorkspaceModelComboBox from '@/modules/workspace/components/WorkspaceModelComboBox.vue'
import { useWorkspaceModels } from '@/modules/workspace/composables/useWorkspaceModels'

const { allowedModels, selectedModel, isLoading, isUpdating, selectModel } = useWorkspaceModels()

const selectedModelId = computed({
  get: () => selectedModel.value?.id ?? '',
  set: (value: string) => {
    if (value) void selectModel(value)
  },
})
</script>

<template>
  <WorkspaceModelComboBox
    v-model="selectedModelId"
    :models="allowedModels"
    :disabled="isLoading || isUpdating"
    :show-browse-all="true"
    trigger-size="sm"
    class="w-full cursor-pointer"
  />
</template>
