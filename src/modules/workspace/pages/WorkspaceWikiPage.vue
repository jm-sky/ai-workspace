<script setup lang="ts">
import { useLocalStorage } from '@vueuse/core'
import {
  BookOpen,
  FileText,
  FolderOpen,
  Info,
  Link2,
  Network,
  PanelLeft,
  PanelLeftClose,
  Plus,
  Trash2,
} from 'lucide-vue-next'
import {
  SplitterGroup,
  SplitterPanel,
  SplitterResizeHandle,
} from 'reka-ui'
import { computed, nextTick, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { toast } from 'vue-sonner'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import ChatLayout from '@/layouts/ChatLayout.vue'
import WikiPageDetail from '@/modules/workspace/components/WikiPageDetail.vue'
import WikiPageList from '@/modules/workspace/components/WikiPageList.vue'
import { useWikiBrowser } from '@/modules/workspace/composables/useWikiBrowser'
import { WIKI_SORT_KEYS, type WikiFolder } from '@/modules/workspace/types/wiki'

const { t } = useI18n()

const FOLDERS: { key: WikiFolder; icon: typeof FolderOpen }[] = [
  { key: 'raw', icon: FileText },
  { key: 'inbox', icon: FolderOpen },
  { key: 'entities', icon: BookOpen },
  { key: 'concepts', icon: BookOpen },
  { key: 'summaries', icon: BookOpen },
  { key: 'meta', icon: BookOpen },
]

const {
  pages,
  total,
  isLoading,
  isSaving,
  error,
  selectedPage,
  activeFolder,
  graphData,
  isGraphLoading,
  filteredPages,
  selectedIds,
  searchQuery,
  sortBy,
  allFilteredSelected,
  loadPages,
  selectPage,
  addPage,
  removePage,
  doDeprecate,
  doIngest,
  loadGraph,
  toggleSelect,
  selectAll,
  clearSelection,
  bulkDelete,
  doPurge,
} = useWikiBrowser()

const activeTab = ref('pages')
const showHelp = ref(false)
const newTitle = ref('')
const newBody = ref('')
const ingestTitle = ref('')
const ingestContent = ref('')
const showIngestDialog = ref(false)
const showNewPageDialog = ref(false)
const showLinkPicker = ref(false)
const showDetailDialog = ref(false)
const linkSearch = ref('')
const bodyTextareaRef = ref<{ $el: HTMLTextAreaElement } | null>(null)
const confirmDeprecateId = ref<string | null>(null)
const showConfirmBulkDelete = ref(false)
const showConfirmPurge = ref(false)
const purgeConfirmText = ref('')
const foldersCollapsed = useLocalStorage('wiki.foldersCollapsed', false)

const activeFolderMeta = computed(() => {
  if (activeFolder.value === null) return null
  return FOLDERS.find((f) => f.key === activeFolder.value) ?? null
})

const filteredForPicker = computed(() => {
  const q = linkSearch.value.trim().toLowerCase()
  if (!q) return pages.value
  return pages.value.filter(
    (p) => p.title.toLowerCase().includes(q) || p.slug.toLowerCase().includes(q),
  )
})

const insertLink = (slug: string) => {
  const el = bodyTextareaRef.value?.$el
  const insert = `[[${slug}]]`
  if (el) {
    const start = el.selectionStart ?? newBody.value.length
    const end = el.selectionEnd ?? start
    newBody.value = newBody.value.slice(0, start) + insert + newBody.value.slice(end)
    void nextTick(() => {
      el.focus()
      el.setSelectionRange(start + insert.length, start + insert.length)
    })
  } else {
    newBody.value += insert
  }
  showLinkPicker.value = false
  linkSearch.value = ''
}

const navigateToLinkedPage = async (
  pageId: string | null | undefined,
  folder?: string | null,
) => {
  if (!pageId) return
  if (folder) {
    activeFolder.value = folder as WikiFolder
  }
  await selectPage(pageId)
}

onMounted(() => {
  void loadPages()
})

const handleFolderClick = (folder: WikiFolder | null) => {
  activeFolder.value = folder
}

const handleAddPage = async () => {
  const title = newTitle.value.trim()
  const body = newBody.value.trim()
  if (!title || !body) return
  try {
    await addPage('inbox', title, body)
    newTitle.value = ''
    newBody.value = ''
    showNewPageDialog.value = false
    toast.success(t('workspace.wiki.pageCreated'))
  } catch {
    toast.error(t('workspace.wiki.createFailed'))
  }
}

const handleDelete = async (pageId: string) => {
  try {
    await removePage(pageId)
    showDetailDialog.value = false
    toast.success(t('workspace.wiki.deleted'))
  } catch {
    toast.error(t('workspace.wiki.deleteFailed'))
  }
}

const handleDeprecate = async () => {
  if (!confirmDeprecateId.value) return
  try {
    await doDeprecate(confirmDeprecateId.value)
    confirmDeprecateId.value = null
    toast.success(t('workspace.wiki.deprecated'))
  } catch {
    toast.error(t('workspace.wiki.deprecateFailed'))
  }
}

const handleIngest = async () => {
  const content = ingestContent.value.trim()
  if (!content) return
  try {
    const result = await doIngest(content, ingestTitle.value.trim() || undefined)
    ingestTitle.value = ''
    ingestContent.value = ''
    showIngestDialog.value = false
    const msg = result.truncated
      ? t('workspace.wiki.ingestTruncated')
      : t('workspace.wiki.ingested')
    toast.success(msg)
  } catch {
    toast.error(t('workspace.wiki.ingestFailed'))
  }
}

const handleBulkDelete = async () => {
  showConfirmBulkDelete.value = false
  try {
    const count = await bulkDelete()
    toast.success(t('workspace.wiki.bulkDeleted', { count }))
    await loadPages()
  } catch {
    toast.error(t('workspace.wiki.bulkDeleteFailed'))
  }
}

const handlePurge = async () => {
  if (purgeConfirmText.value !== 'PURGE') return
  showConfirmPurge.value = false
  purgeConfirmText.value = ''
  try {
    const count = await doPurge()
    showDetailDialog.value = false
    toast.success(t('workspace.wiki.purged', { count }))
  } catch {
    toast.error(t('workspace.wiki.purgeFailed'))
  }
}

const handleTabChange = (tab: string | number) => {
  const next = String(tab)
  activeTab.value = next
  if (next === 'graph') {
    void loadGraph()
  }
}

const svgRef = ref<SVGSVGElement | null>(null)
</script>

<template>
  <ChatLayout>
    <div class="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden px-4 py-3 sm:px-6">
      <!-- Header -->
      <div class="flex shrink-0 items-center justify-between">
        <div class="flex items-center gap-2">
          <BookOpen class="size-5 text-muted-foreground" />
          <div>
            <h1 class="text-lg font-semibold">
              {{ t('workspace.wiki.title') }}
            </h1>
            <p class="text-sm text-muted-foreground">
              {{ t('workspace.wiki.subtitle') }}
            </p>
          </div>
        </div>
        <div class="flex gap-2">
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger as-child>
                <Button
                  size="sm"
                  variant="ghost"
                  class="size-8 p-0"
                  @click="showHelp = !showHelp"
                >
                  <Info class="size-4 text-muted-foreground" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>{{ t('workspace.wiki.help.howItWorks') }}</TooltipContent>
            </Tooltip>
          </TooltipProvider>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger as-child>
                <Button
                  size="sm"
                  variant="outline"
                  @click="showNewPageDialog = true"
                >
                  <Plus class="size-4" />
                  {{ t('workspace.wiki.newPage') }}
                </Button>
              </TooltipTrigger>
              <TooltipContent>{{ t('workspace.wiki.help.newPage') }}</TooltipContent>
            </Tooltip>
          </TooltipProvider>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger as-child>
                <Button
                  size="sm"
                  variant="outline"
                  @click="showIngestDialog = true"
                >
                  <FileText class="size-4" />
                  {{ t('workspace.wiki.ingest') }}
                </Button>
              </TooltipTrigger>
              <TooltipContent>{{ t('workspace.wiki.help.ingest') }}</TooltipContent>
            </Tooltip>
          </TooltipProvider>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger as-child>
                <Button
                  size="sm"
                  variant="destructive"
                  @click="showConfirmPurge = true"
                >
                  <Trash2 class="size-4" />
                  {{ t('workspace.wiki.purgeAll') }}
                </Button>
              </TooltipTrigger>
              <TooltipContent>{{ t('workspace.wiki.help.purgeAll') }}</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      </div>

      <!-- Help banner -->
      <div
        v-if="showHelp"
        class="shrink-0 rounded-xl border border-hairline bg-blue-50/50 px-4 py-3 text-sm dark:bg-blue-950/20"
      >
        <p class="mb-1 font-medium text-foreground">
          {{ t('workspace.wiki.help.howItWorks') }}
        </p>
        <p class="text-muted-foreground">
          {{ t('workspace.wiki.help.howItWorksBody') }}
        </p>
      </div>

      <p v-if="error" class="shrink-0 text-sm text-destructive">
        {{ error }}
      </p>

      <Tabs
        :model-value="activeTab"
        class="flex min-h-0 flex-1 flex-col"
        @update:model-value="handleTabChange"
      >
        <TabsList class="shrink-0">
          <TabsTrigger value="pages">
            {{ t('workspace.wiki.tabs.pages') }}
          </TabsTrigger>
          <TabsTrigger value="graph">
            {{ t('workspace.wiki.tabs.graph') }}
          </TabsTrigger>
        </TabsList>

        <!-- Pages tab -->
        <TabsContent
          value="pages"
          class="flex min-h-0 flex-1 gap-3 overflow-hidden"
        >
          <!-- Folder tree (collapsed) -->
          <div
            v-if="foldersCollapsed"
            class="flex w-9 shrink-0 flex-col items-center gap-1 rounded-xl border border-hairline bg-surface-raised p-1"
          >
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger as-child>
                  <Button
                    variant="ghost"
                    size="icon"
                    class="size-7"
                    :aria-label="t('workspace.wiki.expandFolders')"
                    @click="foldersCollapsed = false"
                  >
                    <PanelLeft class="size-3.5" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="right">
                  {{ t('workspace.wiki.expandFolders') }}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger as-child>
                  <button
                    type="button"
                    class="flex size-7 items-center justify-center rounded-md transition-colors hover:bg-muted"
                    :class="{ 'bg-muted': activeFolder === null }"
                    @click="handleFolderClick(null)"
                  >
                    <FolderOpen class="size-3.5" />
                  </button>
                </TooltipTrigger>
                <TooltipContent side="right">
                  {{ t('workspace.wiki.allFolders') }}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            <TooltipProvider
              v-for="f in FOLDERS"
              :key="f.key"
            >
              <Tooltip>
                <TooltipTrigger as-child>
                  <button
                    type="button"
                    class="flex size-7 items-center justify-center rounded-md transition-colors hover:bg-muted"
                    :class="{ 'bg-muted': activeFolder === f.key }"
                    @click="handleFolderClick(f.key)"
                  >
                    <component :is="f.icon" class="size-3.5" />
                  </button>
                </TooltipTrigger>
                <TooltipContent side="right">
                  {{ t(`workspace.wiki.folders.${f.key}`) }}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>

          <!-- Folder tree (expanded) -->
          <div
            v-else
            class="flex w-40 shrink-0 flex-col gap-1 overflow-y-auto rounded-xl border border-hairline bg-surface-raised p-2"
          >
            <div class="mb-1 flex items-center justify-end">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger as-child>
                    <Button
                      variant="ghost"
                      size="icon"
                      class="size-6"
                      :aria-label="t('workspace.wiki.collapseFolders')"
                      @click="foldersCollapsed = true"
                    >
                      <PanelLeftClose class="size-3.5" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="right">
                    {{ t('workspace.wiki.collapseFolders') }}
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
            <button
              class="flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-xs transition-colors hover:bg-muted"
              :class="{ 'bg-muted font-medium': activeFolder === null }"
              @click="handleFolderClick(null)"
            >
              <FolderOpen class="size-3.5" />
              {{ t('workspace.wiki.allFolders') }}
            </button>
            <TooltipProvider
              v-for="f in FOLDERS"
              :key="f.key"
            >
              <Tooltip>
                <TooltipTrigger as-child>
                  <button
                    class="flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-xs transition-colors hover:bg-muted"
                    :class="{ 'bg-muted font-medium': activeFolder === f.key }"
                    @click="handleFolderClick(f.key)"
                  >
                    <component :is="f.icon" class="size-3.5" />
                    {{ t(`workspace.wiki.folders.${f.key}`) }}
                  </button>
                </TooltipTrigger>
                <TooltipContent side="right">
                  {{ t(`workspace.wiki.help.folders.${f.key}`) }}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>

          <!-- Page list + detail -->
          <div class="flex min-h-0 flex-1 flex-col gap-2 overflow-hidden">
            <!-- Search + sort + selection toolbar -->
            <div class="flex shrink-0 items-center gap-2">
              <TooltipProvider v-if="foldersCollapsed">
                <Tooltip>
                  <TooltipTrigger as-child>
                    <Button
                      variant="ghost"
                      size="icon"
                      class="size-8 shrink-0"
                      :aria-label="t('workspace.wiki.expandFolders')"
                      @click="foldersCollapsed = false"
                    >
                      <PanelLeft class="size-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    {{ activeFolderMeta
                      ? t(`workspace.wiki.folders.${activeFolderMeta.key}`)
                      : t('workspace.wiki.expandFolders') }}
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
              <Input
                v-model="searchQuery"
                :placeholder="t('workspace.wiki.searchPlaceholder')"
                class="h-8 flex-1 text-sm"
              />
              <Select v-model="sortBy">
                <SelectTrigger
                  size="sm"
                  class="h-8 w-44 shrink-0 cursor-pointer sm:w-52"
                  :aria-label="t('workspace.wiki.sortBy')"
                >
                  <SelectValue :placeholder="t('workspace.wiki.sortBy')" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem
                    v-for="key in WIKI_SORT_KEYS"
                    :key="key"
                    :value="key"
                  >
                    {{ t(`workspace.wiki.sort.${key}`) }}
                  </SelectItem>
                </SelectContent>
              </Select>
              <div
                v-if="selectedIds.size > 0"
                class="flex items-center gap-2"
              >
                <span class="text-xs text-muted-foreground">
                  {{ t('workspace.wiki.selectedCount', { count: selectedIds.size }) }}
                </span>
                <Button
                  size="sm"
                  variant="destructive"
                  class="h-8"
                  @click="showConfirmBulkDelete = true"
                >
                  <Trash2 class="size-3.5" />
                  {{ t('workspace.wiki.deleteSelected') }}
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  class="h-8"
                  @click="clearSelection"
                >
                  {{ t('workspace.wiki.clearSelection') }}
                </Button>
              </div>
            </div>

            <!-- List only (no selection) -->
            <div
              v-if="!selectedPage"
              class="min-h-0 flex-1 overflow-hidden"
            >
              <WikiPageList
                :pages="filteredPages"
                :selected-ids="selectedIds"
                :is-loading="isLoading"
                :all-filtered-selected="allFilteredSelected"
                @select-page="selectPage"
                @toggle-select="toggleSelect"
                @select-all="selectAll"
                @clear-selection="clearSelection"
              />
            </div>

            <!-- List + resizable detail -->
            <SplitterGroup
              v-else
              id="wiki-list-detail"
              auto-save-id="wiki-detail-panels"
              direction="horizontal"
              class="flex min-h-0 flex-1 overflow-hidden"
            >
              <SplitterPanel
                id="wiki-list"
                :default-size="60"
                :min-size="30"
                :order="1"
                class="min-h-0 overflow-hidden"
              >
                <WikiPageList
                  :pages="filteredPages"
                  :selected-ids="selectedIds"
                  :selected-page-id="selectedPage.id"
                  :is-loading="isLoading"
                  :all-filtered-selected="allFilteredSelected"
                  @select-page="selectPage"
                  @toggle-select="toggleSelect"
                  @select-all="selectAll"
                  @clear-selection="clearSelection"
                />
              </SplitterPanel>

              <SplitterResizeHandle
                id="wiki-list-detail-handle"
                class="group relative mx-1.5 flex w-1.5 shrink-0 items-center justify-center rounded-full bg-border transition-colors hover:bg-primary/40 data-[state=drag]:bg-primary/50"
              >
                <div class="h-8 w-0.5 rounded-full bg-muted-foreground/30 group-hover:bg-primary/60 group-data-[state=drag]:bg-primary" />
              </SplitterResizeHandle>

              <SplitterPanel
                id="wiki-detail"
                :default-size="40"
                :min-size="25"
                :max-size="70"
                :order="2"
                class="min-h-0 overflow-hidden"
              >
                <div class="flex size-full flex-col overflow-hidden rounded-xl border border-hairline bg-surface-raised p-4">
                  <WikiPageDetail
                    :page="selectedPage"
                    show-expand
                    @deprecate="confirmDeprecateId = $event"
                    @delete="handleDelete"
                    @expand="showDetailDialog = true"
                    @navigate-link="(id, folder) => navigateToLinkedPage(id, folder)"
                  />
                </div>
              </SplitterPanel>
            </SplitterGroup>
          </div>
        </TabsContent>

        <!-- Graph tab -->
        <TabsContent
          value="graph"
          class="flex min-h-0 flex-1 flex-col"
        >
          <div class="flex min-h-0 flex-1 items-center justify-center rounded-xl border border-hairline bg-surface-canvas">
            <p
              v-if="isGraphLoading"
              class="text-sm text-muted-foreground"
            >
              {{ t('workspace.wiki.graphLoading') }}
            </p>
            <div
              v-else-if="graphData && graphData.nodes.length > 0"
              class="size-full"
            >
              <svg
                ref="svgRef"
                class="size-full"
                viewBox="0 0 800 600"
              >
                <line
                  v-for="(edge, i) in graphData.edges"
                  :key="'e-' + i"
                  :x1="100 + ((graphData.nodes.findIndex((n) => n.id === edge.fromId) * 137) % 700)"
                  :y1="80 + ((graphData.nodes.findIndex((n) => n.id === edge.fromId) * 97) % 450)"
                  :x2="100 + ((graphData.nodes.findIndex((n) => n.id === (edge.toId || '')) * 137) % 700)"
                  :y2="80 + ((graphData.nodes.findIndex((n) => n.id === (edge.toId || '')) * 97) % 450)"
                  stroke="currentColor"
                  stroke-opacity="0.2"
                  stroke-width="1"
                />
                <g
                  v-for="(node, i) in graphData.nodes"
                  :key="node.id"
                  class="cursor-pointer"
                  @click="selectPage(node.id); activeTab = 'pages'"
                >
                  <circle
                    :cx="100 + ((i * 137) % 700)"
                    :cy="80 + ((i * 97) % 450)"
                    r="6"
                    :fill="node.folder === 'raw' ? '#ef4444' : node.folder === 'meta' ? '#6366f1' : '#22c55e'"
                    opacity="0.8"
                  />
                  <text
                    :x="100 + ((i * 137) % 700)"
                    :y="80 + ((i * 97) % 450) + 16"
                    text-anchor="middle"
                    class="fill-current text-[9px]"
                  >
                    {{ node.slug.slice(0, 20) }}
                  </text>
                </g>
              </svg>
            </div>
            <div
              v-else
              class="flex flex-col items-center gap-2 text-sm text-muted-foreground"
            >
              <Network class="size-8 opacity-40" />
              {{ t('workspace.wiki.graphEmpty') }}
            </div>
          </div>
        </TabsContent>
      </Tabs>

      <p class="shrink-0 text-xs text-muted-foreground">
        {{ t('workspace.wiki.total', { count: total }) }}
      </p>
    </div>

    <!-- Detail expand dialog -->
    <Dialog
      :open="showDetailDialog && selectedPage !== null"
      @update:open="(open) => { if (!open) showDetailDialog = false }"
    >
      <DialogContent class="flex h-[85vh] max-w-5xl flex-col gap-0 border-hairline bg-surface-raised p-4 sm:max-w-5xl">
        <DialogHeader class="sr-only">
          <DialogTitle>
            {{ selectedPage?.title }}
          </DialogTitle>
        </DialogHeader>
        <div
          v-if="selectedPage"
          class="min-h-0 flex-1 overflow-hidden pr-6 pt-1"
        >
          <WikiPageDetail
            :page="selectedPage"
            @deprecate="confirmDeprecateId = $event"
            @delete="handleDelete"
            @navigate-link="(id, folder) => navigateToLinkedPage(id, folder)"
          />
        </div>
      </DialogContent>
    </Dialog>

    <!-- New page dialog -->
    <Dialog
      :open="showNewPageDialog"
      @update:open="(open) => { if (!open) showNewPageDialog = false }"
    >
      <DialogContent class="max-w-lg border-hairline bg-surface-raised">
        <DialogHeader>
          <DialogTitle>{{ t('workspace.wiki.newPage') }}</DialogTitle>
        </DialogHeader>
        <div class="space-y-3">
          <div>
            <Label>{{ t('workspace.wiki.pageTitle') }}</Label>
            <Input
              v-model="newTitle"
              :placeholder="t('workspace.wiki.titlePlaceholder')"
            />
          </div>
          <div>
            <div class="mb-1 flex items-center justify-between">
              <Label>{{ t('workspace.wiki.pageBody') }}</Label>
              <Button
                size="sm"
                variant="ghost"
                class="h-6 gap-1 px-2 text-xs"
                type="button"
                @click="showLinkPicker = true"
              >
                <Link2 class="size-3" />
                {{ t('workspace.wiki.help.linkPicker.insert') }}
              </Button>
            </div>
            <Textarea
              ref="bodyTextareaRef"
              v-model="newBody"
              :placeholder="t('workspace.wiki.bodyPlaceholder')"
              rows="6"
            />
            <p class="mt-1 text-xs text-muted-foreground">
              {{ t('workspace.wiki.help.newPageLinkHint') }}
            </p>
          </div>
          <div class="flex justify-end">
            <Button
              :disabled="isSaving || !newTitle.trim() || !newBody.trim()"
              @click="handleAddPage"
            >
              {{ t('workspace.wiki.createAction') }}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>

    <!-- Ingest dialog -->
    <Dialog
      :open="showIngestDialog"
      @update:open="(open) => { if (!open) showIngestDialog = false }"
    >
      <DialogContent class="flex max-h-[90vh] max-w-lg flex-col border-hairline bg-surface-raised">
        <DialogHeader class="shrink-0">
          <DialogTitle>{{ t('workspace.wiki.ingestTitle') }}</DialogTitle>
        </DialogHeader>
        <div class="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto">
          <p class="text-sm text-muted-foreground">
            {{ t('workspace.wiki.help.ingestDialogHint') }}
          </p>
          <div>
            <Label>{{ t('workspace.wiki.ingestTitleLabel') }}</Label>
            <Input
              v-model="ingestTitle"
              :placeholder="t('workspace.wiki.ingestTitlePlaceholder')"
            />
          </div>
          <div>
            <Label>{{ t('workspace.wiki.ingestContentLabel') }}</Label>
            <Textarea
              v-model="ingestContent"
              :placeholder="t('workspace.wiki.ingestContentPlaceholder')"
              rows="8"
              class="min-h-[160px]"
            />
          </div>
        </div>
        <div class="shrink-0 pt-2 flex justify-end">
          <Button
            :disabled="isSaving || !ingestContent.trim()"
            @click="handleIngest"
          >
            {{ t('workspace.wiki.ingestAction') }}
          </Button>
        </div>
      </DialogContent>
    </Dialog>

    <!-- Deprecate confirm dialog -->
    <Dialog
      :open="confirmDeprecateId !== null"
      @update:open="(open) => { if (!open) confirmDeprecateId = null }"
    >
      <DialogContent class="max-w-sm border-hairline bg-surface-raised">
        <DialogHeader>
          <DialogTitle>{{ t('workspace.wiki.confirmDeprecate') }}</DialogTitle>
        </DialogHeader>
        <p class="text-sm text-muted-foreground">
          {{ t('workspace.wiki.confirmDeprecateDesc') }}
        </p>
        <div class="flex justify-end gap-2">
          <Button
            variant="outline"
            @click="confirmDeprecateId = null"
          >
            {{ t('workspace.wiki.cancel') }}
          </Button>
          <Button
            variant="destructive"
            @click="handleDeprecate"
          >
            {{ t('workspace.wiki.deprecateAction') }}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
    <!-- Link Picker dialog -->
    <Dialog
      :open="showLinkPicker"
      @update:open="(open) => { if (!open) { showLinkPicker = false; linkSearch = '' } }"
    >
      <DialogContent class="max-w-md border-hairline bg-surface-raised">
        <DialogHeader>
          <DialogTitle>{{ t('workspace.wiki.help.linkPicker.title') }}</DialogTitle>
        </DialogHeader>
        <p class="text-xs text-muted-foreground">
          {{ t('workspace.wiki.help.linkPicker.hint') }}
        </p>
        <Input
          v-model="linkSearch"
          :placeholder="t('workspace.wiki.help.linkPicker.search')"
          autofocus
        />
        <div class="max-h-64 overflow-y-auto rounded-lg border border-hairline">
          <p
            v-if="filteredForPicker.length === 0"
            class="p-3 text-sm text-muted-foreground"
          >
            {{ t('workspace.wiki.help.linkPicker.empty') }}
          </p>
          <ul v-else class="divide-y divide-hairline">
            <li
              v-for="page in filteredForPicker"
              :key="page.id"
              class="flex cursor-pointer flex-col gap-0.5 px-3 py-2 transition-colors hover:bg-muted/50"
              @click="insertLink(page.slug)"
            >
              <span class="text-sm font-medium">{{ page.title }}</span>
              <span class="font-mono text-xs text-muted-foreground">{{ page.slug }}</span>
            </li>
          </ul>
        </div>
      </DialogContent>
    </Dialog>

    <!-- Bulk delete confirm dialog -->
    <Dialog
      :open="showConfirmBulkDelete"
      @update:open="(open) => { if (!open) showConfirmBulkDelete = false }"
    >
      <DialogContent class="max-w-sm border-hairline bg-surface-raised">
        <DialogHeader>
          <DialogTitle>{{ t('workspace.wiki.confirmBulkDelete') }}</DialogTitle>
        </DialogHeader>
        <p class="text-sm text-muted-foreground">
          {{ t('workspace.wiki.confirmBulkDeleteDesc', { count: selectedIds.size }) }}
        </p>
        <div class="flex justify-end gap-2">
          <Button
            variant="outline"
            @click="showConfirmBulkDelete = false"
          >
            {{ t('workspace.wiki.cancel') }}
          </Button>
          <Button
            variant="destructive"
            @click="handleBulkDelete"
          >
            {{ t('workspace.wiki.deleteSelected') }}
          </Button>
        </div>
      </DialogContent>
    </Dialog>

    <!-- Purge all confirm dialog -->
    <Dialog
      :open="showConfirmPurge"
      @update:open="(open) => { if (!open) { showConfirmPurge = false; purgeConfirmText = '' } }"
    >
      <DialogContent class="max-w-sm border-hairline bg-surface-raised">
        <DialogHeader>
          <DialogTitle>{{ t('workspace.wiki.confirmPurge') }}</DialogTitle>
        </DialogHeader>
        <p class="text-sm text-muted-foreground">
          {{ t('workspace.wiki.confirmPurgeDesc') }}
        </p>
        <div class="space-y-2">
          <Label class="text-xs">{{ t('workspace.wiki.purgeConfirmLabel') }}</Label>
          <Input
            v-model="purgeConfirmText"
            placeholder="PURGE"
            class="font-mono"
          />
        </div>
        <div class="flex justify-end gap-2">
          <Button
            variant="outline"
            @click="showConfirmPurge = false; purgeConfirmText = ''"
          >
            {{ t('workspace.wiki.cancel') }}
          </Button>
          <Button
            variant="destructive"
            :disabled="purgeConfirmText !== 'PURGE'"
            @click="handlePurge"
          >
            {{ t('workspace.wiki.purgeAll') }}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  </ChatLayout>
</template>
