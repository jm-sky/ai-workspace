<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { toast } from 'vue-sonner'
import { secureMarkdownHtml } from '@/shared/utils/markdownPostProcess'

const { content } = defineProps<{
  content: string
}>()

const { t } = useI18n()

const mdInstance = ref<InstanceType<typeof import('markdown-it').default> | null>(null)

const COPY_ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="size-3.5"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>'

function withCopyButton(inner: string, copyTarget: 'pre' | 'blockquote'): string {
  return '<div class="md-copy-wrap relative">'
    + `<button type="button" class="md-copy-btn absolute right-2 top-2 z-10 inline-flex items-center justify-center rounded-md border border-hairline bg-surface-raised/90 p-1.5 text-muted-foreground opacity-70 shadow-sm transition hover:text-foreground hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" data-copy-target="${copyTarget}" aria-label="${t('workspace.chat.copyBlock')}" title="${t('workspace.chat.copyBlock')}">${COPY_ICON}</button>`
    + inner
    + '</div>'
}

onMounted(async () => {
  const MarkdownItModule = await import('markdown-it')
  const md = new MarkdownItModule.default({
    html: false,
    linkify: true,
    typographer: true,
    breaks: true,
  })
  md.renderer.rules.table_open = () => '<div class="table-wrap"><table>'
  md.renderer.rules.table_close = () => '</table></div>'

  const defaultFence = md.renderer.rules.fence?.bind(md.renderer.rules)
    ?? ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options))
  md.renderer.rules.fence = (tokens, idx, options, env, self) =>
    withCopyButton(defaultFence(tokens, idx, options, env, self), 'pre')

  const defaultCodeBlock = md.renderer.rules.code_block?.bind(md.renderer.rules)
    ?? ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options))
  md.renderer.rules.code_block = (tokens, idx, options, env, self) =>
    withCopyButton(defaultCodeBlock(tokens, idx, options, env, self), 'pre')

  md.renderer.rules.blockquote_open = () => '<div class="md-copy-wrap relative group/quote"><blockquote>'
  md.renderer.rules.blockquote_close = () =>
    `</blockquote><button type="button" class="md-copy-btn absolute right-2 top-2 z-10 inline-flex items-center justify-center rounded-md border border-hairline bg-surface-raised/90 p-1.5 text-muted-foreground opacity-70 shadow-sm transition hover:text-foreground hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" data-copy-target="blockquote" aria-label="${t('workspace.chat.copyBlock')}" title="${t('workspace.chat.copyBlock')}">${COPY_ICON}</button></div>`

  mdInstance.value = md
})

const rendered = computed(() => {
  if (!mdInstance.value) return content
  return secureMarkdownHtml(mdInstance.value.render(content))
})

const onMarkdownClick = async (event: MouseEvent) => {
  const btn = (event.target as HTMLElement).closest<HTMLElement>('.md-copy-btn')
  if (!btn) return

  const wrap = btn.closest('.md-copy-wrap')
  const target = btn.dataset.copyTarget === 'blockquote'
    ? wrap?.querySelector('blockquote')
    : wrap?.querySelector('pre')
  const text = target?.textContent ?? ''
  if (!text) return

  try {
    await navigator.clipboard.writeText(text)
    toast.success(t('workspace.chat.copied'))
  } catch {
    toast.error(t('workspace.chat.copyFailed'))
  }
}
</script>

<template>
  <!-- eslint-disable-next-line vue/no-v-html -->
  <div
    class="agent-md max-w-none text-sm leading-relaxed text-foreground"
    @click="onMarkdownClick"
    v-html="rendered"
  />
</template>
