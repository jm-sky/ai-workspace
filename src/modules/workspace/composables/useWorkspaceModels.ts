import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, ref, watch } from 'vue'
import { listAiModels } from '@/modules/workspace/services/aiModelsApiService'
import {
  getEffectiveWorkspaceConfig,
  setUserDefaultModel,
} from '@/modules/workspace/services/workspaceConfigApiService'
import type {
  IAiModel,
  IEffectiveWorkspaceConfig,
} from '@/modules/workspace/types/workspaceConfig'

export const workspaceModelsQueryKeys = {
  all: ['workspace-models'] as const,
  config: () => [...workspaceModelsQueryKeys.all, 'config'] as const,
  catalog: () => [...workspaceModelsQueryKeys.all, 'catalog'] as const,
}

const selectedModelId = ref<string | null>(null)

/** Fallback when no persisted default is present in the catalog. */
export function pickDefaultModelId(
  models: IAiModel[],
  defaultModel?: string | null,
): string | null {
  if (models.length === 0) return null
  if (defaultModel && models.some((m) => m.id === defaultModel)) {
    return defaultModel
  }
  const recommended = models.find((m) => m.recommended)
  return recommended?.id ?? models[0]?.id ?? null
}

/**
 * Resolve which model id the picker should show.
 *
 * Waits for workspace config before falling back to "recommended", otherwise a
 * fast catalog response would pin Claude and ignore the saved default on refresh.
 */
export function resolveSelectedModelId(opts: {
  models: IAiModel[]
  defaultModel?: string | null
  configFetched: boolean
  currentSelectedId: string | null
}): string | null {
  const { models, defaultModel, configFetched, currentSelectedId } = opts
  if (models.length === 0 || !configFetched) {
    return currentSelectedId
  }
  if (defaultModel && models.some((m) => m.id === defaultModel)) {
    return defaultModel
  }
  if (currentSelectedId && models.some((m) => m.id === currentSelectedId)) {
    return currentSelectedId
  }
  return pickDefaultModelId(models, defaultModel)
}

export function useWorkspaceModels() {
  const queryClient = useQueryClient()

  const configQuery = useQuery({
    queryKey: workspaceModelsQueryKeys.config(),
    queryFn: getEffectiveWorkspaceConfig,
    staleTime: 5 * 60 * 1000,
  })

  const catalogQuery = useQuery({
    queryKey: workspaceModelsQueryKeys.catalog(),
    queryFn: listAiModels,
    staleTime: 30 * 60 * 1000,
  })

  /**
   * The models the user may actually pick. An empty allow-list means the
   * workspace sets no ceiling, so the whole catalog is fair game.
   */
  const allowedModels = computed<IAiModel[]>(() => {
    const allowed = configQuery.data.value?.allowedModels ?? []
    const catalog = catalogQuery.data.value?.models ?? []
    if (allowed.length === 0) return catalog
    const allowedSet = new Set(allowed)
    const filtered = catalog.filter((model) => allowedSet.has(model.id))
    if (filtered.length === 0 && catalog.length > 0) return catalog
    return filtered
  })

  watch(
    [
      () => configQuery.data.value?.defaultModel,
      allowedModels,
      () => configQuery.isFetched.value,
    ],
    ([defaultModel, models, configFetched]) => {
      selectedModelId.value = resolveSelectedModelId({
        models,
        defaultModel,
        configFetched,
        currentSelectedId: selectedModelId.value,
      })
    },
    { immediate: true },
  )

  const selectedModel = computed<IAiModel | undefined>(() =>
    allowedModels.value.find((m) => m.id === selectedModelId.value),
  )

  const hasValidModel = computed(() => !!selectedModel.value)

  const selectModelMutation = useMutation({
    mutationFn: (modelId: string) => setUserDefaultModel(modelId),
    onError: async () => {
      await queryClient.invalidateQueries({ queryKey: workspaceModelsQueryKeys.config() })
    },
  })

  const selectModel = async (modelId: string) => {
    selectedModelId.value = modelId
    // Keep the watch in sync with the optimistic choice until refetch lands.
    queryClient.setQueryData<IEffectiveWorkspaceConfig>(
      workspaceModelsQueryKeys.config(),
      (old) => (old ? { ...old, defaultModel: modelId } : old),
    )
    try {
      await selectModelMutation.mutateAsync(modelId)
      await queryClient.invalidateQueries({ queryKey: workspaceModelsQueryKeys.config() })
    } catch {
      // onError already invalidates; selection will snap back to persisted default
    }
  }

  const getSelectedModelId = () => selectedModelId.value ?? undefined

  return {
    allowedModels,
    selectedModel,
    selectedModelId,
    configQuery,
    catalogQuery,
    isLoading: computed(() => configQuery.isLoading.value || catalogQuery.isLoading.value),
    isUpdating: computed(() => selectModelMutation.isPending.value),
    selectModel,
    getSelectedModelId,
    hasValidModel,
  }
}
