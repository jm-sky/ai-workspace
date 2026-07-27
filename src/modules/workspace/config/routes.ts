import type { RouteRecordRaw } from 'vue-router'

export const WorkspaceRouteName = {
  Chat: 'workspace-chat',
  Memory: 'workspace-memory',
  Knowledge: 'workspace-knowledge',
  Wiki: 'workspace-wiki',
  Settings: 'workspace-settings',
  SettingsModels: 'workspace-settings-models',
  SettingsIntegrations: 'workspace-settings-integrations',
} as const

export const WorkspaceRoutePath = {
  Chat: '/workspace',
  Memory: '/workspace/memory',
  Knowledge: '/workspace/knowledge',
  Wiki: '/workspace/wiki',
  Settings: '/workspace/settings',
  SettingsModels: '/workspace/settings/models',
  SettingsIntegrations: '/workspace/settings/integrations',
} as const

export const workspaceRoutes: RouteRecordRaw[] = [
  {
    path: WorkspaceRoutePath.Chat,
    name: WorkspaceRouteName.Chat,
    component: () => import('../pages/WorkspaceChatPage.vue'),
    meta: { layout: 'authenticated', requiresAuth: true, requiresTenant: true, title: 'workspace.chat.title' },
  },
  {
    path: WorkspaceRoutePath.Memory,
    name: WorkspaceRouteName.Memory,
    component: () => import('../pages/WorkspaceMemoryPage.vue'),
    meta: { layout: 'authenticated', requiresAuth: true, requiresTenant: true, title: 'workspace.memory.title' },
  },
  {
    path: WorkspaceRoutePath.Knowledge,
    name: WorkspaceRouteName.Knowledge,
    component: () => import('../pages/WorkspaceKnowledgePage.vue'),
    meta: { layout: 'authenticated', requiresAuth: true, requiresTenant: true, title: 'workspace.knowledge.title' },
  },
  {
    path: WorkspaceRoutePath.Wiki,
    name: WorkspaceRouteName.Wiki,
    component: () => import('../pages/WorkspaceWikiPage.vue'),
    meta: { layout: 'authenticated', requiresAuth: true, requiresTenant: true, title: 'workspace.wiki.title' },
  },
  {
    path: WorkspaceRoutePath.Settings,
    component: () => import('../layouts/WorkspaceSettingsLayout.vue'),
    meta: { requiresAuth: true, requiresTenant: true },
    children: [
      {
        path: '',
        redirect: { name: WorkspaceRouteName.SettingsModels },
      },
      {
        path: 'models',
        name: WorkspaceRouteName.SettingsModels,
        component: () => import('../pages/WorkspaceModelsSettingsPage.vue'),
        meta: { title: 'workspace.settings.models' },
      },
      {
        path: 'integrations',
        name: WorkspaceRouteName.SettingsIntegrations,
        component: () => import('../pages/WorkspaceIntegrationsSettingsPage.vue'),
        meta: { title: 'workspace.settings.integrations' },
      },
    ],
  },
]
