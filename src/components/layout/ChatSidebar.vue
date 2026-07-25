<script setup lang="ts">
import { BookOpen, Brain, Info, Settings as SettingsIcon } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute } from 'vue-router'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from '@/components/ui/sidebar'
import SessionHistoryList from '@/modules/workspace/components/SessionHistoryList.vue'
import { useChatSessionNavContext } from '@/modules/workspace/composables/useChatSessionNav'
import { WorkspaceRoutePath } from '@/modules/workspace/routes'
import { PublicRoutePaths } from '@/router/publicRoutes'

const { t } = useI18n()
const route = useRoute()
const { isMobile, setOpenMobile } = useSidebar()

const {
  sessionsLoading,
  searchQuery,
  filteredSessions,
  activeSessionId,
  selectSession,
  newChat,
} = useChatSessionNavContext()

const closeMobileIfNeeded = () => {
  if (isMobile.value) {
    setOpenMobile(false)
  }
}

const handleSelect = async (sessionId: string) => {
  await selectSession(sessionId)
  closeMobileIfNeeded()
}

const handleNewChat = async () => {
  await newChat()
  closeMobileIfNeeded()
}
</script>

<template>
  <Sidebar collapsible="offcanvas" class="bg-sidebar-mist">
    <SidebarContent class="flex min-h-0 flex-col overflow-hidden p-0">
      <SidebarGroup class="flex min-h-0 flex-1 flex-col p-0">
        <SidebarGroupContent class="flex min-h-0 flex-1 flex-col">
          <SessionHistoryList
            :sessions="filteredSessions"
            :active-session-id="activeSessionId"
            :is-loading="sessionsLoading"
            :search-query="searchQuery"
            @update:search-query="searchQuery = $event"
            @select="handleSelect"
            @new-chat="handleNewChat"
          />
        </SidebarGroupContent>
      </SidebarGroup>
    </SidebarContent>

    <SidebarFooter>
      <SidebarMenu>
        <SidebarMenuItem>
          <RouterLink
            v-slot="{ href, navigate, isActive }"
            :to="WorkspaceRoutePath.Memory"
            custom
          >
            <SidebarMenuButton
              :is-active="isActive || route.path.startsWith(WorkspaceRoutePath.Memory)"
              as="a"
              :href="href"
              @click="navigate"
            >
              <Brain class="size-4" />
              <span>{{ t('workspace.nav.memory') }}</span>
            </SidebarMenuButton>
          </RouterLink>
        </SidebarMenuItem>

        <SidebarMenuItem>
          <RouterLink
            v-slot="{ href, navigate, isActive }"
            :to="WorkspaceRoutePath.Knowledge"
            custom
          >
            <SidebarMenuButton
              :is-active="isActive || route.path.startsWith(WorkspaceRoutePath.Knowledge)"
              as="a"
              :href="href"
              @click="navigate"
            >
              <BookOpen class="size-4" />
              <span>{{ t('workspace.nav.knowledge') }}</span>
            </SidebarMenuButton>
          </RouterLink>
        </SidebarMenuItem>

        <SidebarMenuItem>
          <RouterLink v-slot="{ href, navigate, isActive }" :to="WorkspaceRoutePath.Settings" custom>
            <SidebarMenuButton
              :is-active="isActive || route.path.startsWith(WorkspaceRoutePath.Settings)"
              as="a"
              :href="href"
              @click="navigate"
            >
              <SettingsIcon class="size-4" />
              <span>{{ t('workspace.nav.workspaceSettings') }}</span>
            </SidebarMenuButton>
          </RouterLink>
        </SidebarMenuItem>

        <SidebarMenuItem>
          <RouterLink v-slot="{ href, navigate, isActive }" :to="PublicRoutePaths.about" custom>
            <SidebarMenuButton
              :is-active="isActive"
              as="a"
              :href="href"
              @click="navigate"
            >
              <Info class="size-4" />
              <span>{{ t('common.pages.about', 'About') }}</span>
            </SidebarMenuButton>
          </RouterLink>
        </SidebarMenuItem>
      </SidebarMenu>
    </SidebarFooter>

    <SidebarRail />
  </Sidebar>
</template>
