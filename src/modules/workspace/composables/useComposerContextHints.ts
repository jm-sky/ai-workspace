import { ref } from 'vue'
import type { ComposerContextProvider, IComposerContextHint } from '@/modules/workspace/types/contextHints'

export function useComposerContextHints() {
  const contextHints = ref<IComposerContextHint[]>([])

  const addContextHint = (provider: ComposerContextProvider) => {
    if (contextHints.value.some((hint) => hint.provider === provider)) return
    contextHints.value = [
      ...contextHints.value,
      { id: `ctx-${provider}-${Date.now()}`, provider },
    ]
  }

  const removeContextHint = (id: string) => {
    contextHints.value = contextHints.value.filter((hint) => hint.id !== id)
  }

  const takeContextHints = (): IComposerContextHint[] => {
    const pending = [...contextHints.value]
    contextHints.value = []
    return pending
  }

  return {
    contextHints,
    addContextHint,
    removeContextHint,
    takeContextHints,
  }
}
