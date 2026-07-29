<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { secureMarkdownHtml } from '@/shared/utils/markdownPostProcess'

const { content } = defineProps<{
  content: string
}>()

const mdInstance = ref<InstanceType<typeof import('markdown-it').default> | null>(null)

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
  mdInstance.value = md
})

const rendered = computed(() => {
  if (!mdInstance.value) return content
  return secureMarkdownHtml(mdInstance.value.render(content))
})
</script>

<template>
  <!-- eslint-disable-next-line vue/no-v-html -->
  <div
    class="agent-md max-w-none text-sm leading-relaxed text-foreground"
    v-html="rendered"
  />
</template>
