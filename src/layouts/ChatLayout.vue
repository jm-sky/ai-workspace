<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ChatHeader from '@/components/layout/ChatHeader.vue'
import ChatSidebar from '@/components/layout/ChatSidebar.vue'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import { useChatSessionNav } from '@/modules/workspace/composables/useChatSessionNav'
import { WorkspaceRoutePath } from '@/modules/workspace/routes'

const route = useRoute()
const router = useRouter()

const activeSessionId = computed(() =>
  typeof route.query.session === 'string' ? route.query.session : null,
)

const loadSession = async (sessionId: string) => {
  await router.push({
    path: WorkspaceRoutePath.Chat,
    query: { session: sessionId },
  })
}

useChatSessionNav({
  activeSessionId,
  loadSession,
})
</script>

<template>
  <SidebarProvider>
    <ChatSidebar class="top-(--header-height) h-[calc(100svh-var(--header-height))] shadow-sidebar" />
    <SidebarInset class="flex h-dvh flex-col overflow-hidden bg-surface-canvas pt-14">
      <ChatHeader>
        <template
          v-if="$slots['header-center']"
          #center
        >
          <slot name="header-center" />
        </template>
      </ChatHeader>
      <main class="flex min-h-0 flex-1 flex-col overflow-hidden">
        <slot />
      </main>
    </SidebarInset>
  </SidebarProvider>
</template>
