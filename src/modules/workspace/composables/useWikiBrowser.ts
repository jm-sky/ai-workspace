import { computed, ref } from 'vue'
import {
  createWikiPage,
  deleteWikiPage,
  deprecateWikiPage,
  getWikiGraph,
  getWikiPage,
  ingestWiki,
  lintWiki,
  listWikiPages,
} from '@/modules/workspace/services/wikiApiService'
import { getApiErrorMessage } from '@/shared/utils/apiError'
import type {
  IWikiGraphResponse,
  IWikiLintResponse,
  IWikiPage,
  IWikiPageDetail,
  WikiFolder,
} from '@/modules/workspace/types/wiki'

export function useWikiBrowser() {
  const pages = ref<IWikiPage[]>([])
  const total = ref(0)
  const isLoading = ref(false)
  const isSaving = ref(false)
  const error = ref<string | null>(null)
  const selectedPage = ref<IWikiPageDetail | null>(null)
  const isPageLoading = ref(false)
  const activeFolder = ref<WikiFolder | null>(null)
  const graphData = ref<IWikiGraphResponse | null>(null)
  const isGraphLoading = ref(false)
  const lintResult = ref<IWikiLintResponse | null>(null)

  const folderCounts = computed(() => {
    const counts: Record<string, number> = {}
    for (const p of pages.value) {
      counts[p.folder] = (counts[p.folder] || 0) + 1
    }
    return counts
  })

  const filteredPages = computed(() => {
    if (!activeFolder.value) return pages.value
    return pages.value.filter((p) => p.folder === activeFolder.value)
  })

  const loadPages = async (options?: { folder?: string; silent?: boolean }) => {
    if (!options?.silent) isLoading.value = true
    error.value = null
    try {
      const response = await listWikiPages({
        folder: options?.folder,
        limit: 500,
        offset: 0,
      })
      pages.value = response.pages
      total.value = response.total
    } catch (err) {
      error.value = getApiErrorMessage(err, 'Failed to load wiki pages')
    } finally {
      isLoading.value = false
    }
  }

  const selectPage = async (pageId: string) => {
    isPageLoading.value = true
    error.value = null
    try {
      selectedPage.value = await getWikiPage(pageId)
    } catch (err) {
      error.value = getApiErrorMessage(err, 'Failed to load page')
    } finally {
      isPageLoading.value = false
    }
  }

  const closePage = () => {
    selectedPage.value = null
  }

  const addPage = async (
    folder: WikiFolder,
    title: string,
    bodyMd: string,
  ) => {
    isSaving.value = true
    error.value = null
    try {
      await createWikiPage({ folder, title, body_md: bodyMd })
      await loadPages()
    } catch (err) {
      error.value = getApiErrorMessage(err, 'Failed to create page')
      throw err
    } finally {
      isSaving.value = false
    }
  }

  const removePage = async (pageId: string) => {
    error.value = null
    try {
      await deleteWikiPage(pageId)
      pages.value = pages.value.filter((p) => p.id !== pageId)
      total.value = Math.max(0, total.value - 1)
      if (selectedPage.value?.id === pageId) {
        selectedPage.value = null
      }
    } catch (err) {
      error.value = getApiErrorMessage(err, 'Failed to delete page')
      throw err
    }
  }

  const doDeprecate = async (pageId: string) => {
    error.value = null
    try {
      const updated = await deprecateWikiPage(pageId)
      const idx = pages.value.findIndex((p) => p.id === pageId)
      if (idx >= 0) pages.value[idx] = updated
      if (selectedPage.value?.id === pageId) {
        selectedPage.value = null
      }
    } catch (err) {
      error.value = getApiErrorMessage(err, 'Failed to deprecate page')
      throw err
    }
  }

  const doIngest = async (content: string, title?: string) => {
    isSaving.value = true
    error.value = null
    try {
      const result = await ingestWiki({ content, title })
      await loadPages()
      return result
    } catch (err) {
      error.value = getApiErrorMessage(err, 'Failed to ingest')
      throw err
    } finally {
      isSaving.value = false
    }
  }

  const loadGraph = async (folder?: string) => {
    isGraphLoading.value = true
    error.value = null
    try {
      graphData.value = await getWikiGraph({ folder })
    } catch (err) {
      error.value = getApiErrorMessage(err, 'Failed to load graph')
    } finally {
      isGraphLoading.value = false
    }
  }

  const runLint = async () => {
    error.value = null
    try {
      lintResult.value = await lintWiki()
    } catch (err) {
      error.value = getApiErrorMessage(err, 'Failed to run lint')
    }
  }

  return {
    pages,
    total,
    isLoading,
    isSaving,
    error,
    selectedPage,
    isPageLoading,
    activeFolder,
    graphData,
    isGraphLoading,
    lintResult,
    folderCounts,
    filteredPages,
    loadPages,
    selectPage,
    closePage,
    addPage,
    removePage,
    doDeprecate,
    doIngest,
    loadGraph,
    runLint,
  }
}
