<script setup lang="ts">
import { CreditCard, Link2, SettingsIcon, ShieldIcon, UserIcon } from 'lucide-vue-next'
import { type Component, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { toast } from 'vue-sonner'
import UserNav from '@/components/layout/UserNav.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import LogoText from '@/components/ui/LogoText.vue'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { AdminRoutePaths } from '@/modules/admin/routes'
import { useAuth } from '@/modules/auth/composables/useAuth'
import { AuthRouteNames } from '@/modules/auth/config/routes'
import { BillingRoutePaths } from '@/modules/billing/routes'
import { SettingsRoutePaths } from '@/modules/settings/routes'
import { useUser } from '@/modules/user/composables/useUser'
import { UserRoutePaths } from '@/modules/user/routes'
import { WorkspaceRoutePath } from '@/modules/workspace/routes'
import DarkModeToggle from '@/shared/components/DarkModeToggle.vue'
import { usePermissions } from '@/shared/composables/usePermissions'
import LocaleToggle from '@/shared/i18n/components/LocaleToggle.vue'

const { t } = useI18n()
const router = useRouter()
const { profile } = useUser()
const { canAccessAdminPanel } = usePermissions()
const { logout, user: authUser } = useAuth()

const user = computed(() => authUser.value ?? profile.value)

interface Link {
  to: string
  label: string
  icon?: Component
  hidden?: boolean
}

const coreLinks = computed<Link[]>(() => [
  {
    to: UserRoutePaths.profile,
    label: t('user.profile.title', 'Profile'),
    icon: UserIcon,
  },
  {
    to: SettingsRoutePaths.account,
    label: t('settings.nav.account', 'Account'),
    icon: SettingsIcon,
  },
  {
    to: SettingsRoutePaths.security,
    label: t('settings.nav.security', 'Security'),
    icon: ShieldIcon,
  },
  {
    to: SettingsRoutePaths.connections,
    label: t('settings.nav.connections', 'Connections'),
    icon: Link2,
  },
  {
    to: BillingRoutePaths.billing,
    label: t('billing.title', 'Billing & Subscription'),
    icon: CreditCard,
  },
  {
    to: AdminRoutePaths.dashboard,
    label: t('admin.dashboard.title', 'Admin Dashboard'),
    icon: ShieldIcon,
    hidden: !canAccessAdminPanel.value,
  },
])

const handleLogout = async () => {
  try {
    await logout()
    toast.success(t('auth.logout_success', 'Logged out successfully'))
    await router.push({ name: AuthRouteNames.login })
  } catch (error) {
    console.error('Logout error:', error)
    toast.error(t('auth.logout_error', 'Failed to logout'))
  }
}
</script>

<template>
  <header class="fixed left-0 top-0 z-50 w-full shrink-0 border-b border-hairline bg-surface-canvas/80 shadow-soft backdrop-blur-md">
    <div class="mx-auto flex h-(--header-height) items-center gap-2 px-2 sm:px-3">
      <div class="flex min-w-0 shrink-0 items-center gap-2 md:w-(--sidebar-width) md:gap-4 md:pl-1">
        <SidebarTrigger class="shrink-0 opacity-70 hover:opacity-100" />
        <RouterLink
          :to="WorkspaceRoutePath.Chat"
          class="flex min-w-0 items-center gap-1.5 transition-opacity hover:opacity-80 sm:gap-2"
        >
          <AppIcon class="size-6 shrink-0 sm:size-7" />
          <LogoText class="hidden truncate sm:inline" />
        </RouterLink>
      </div>

      <div
        v-if="$slots.center"
        class="flex min-w-0 flex-1 items-center justify-center overflow-hidden px-1"
      >
        <slot name="center" />
      </div>

      <div class="ml-auto flex shrink-0 items-center justify-end gap-1 mr-2">
        <nav class="flex items-center gap-x-1">
          <LocaleToggle />
          <DarkModeToggle />
          <UserNav
            :core-links
            :user-name="user?.name ?? t('user.guest')"
            :user-email="user?.email"
            :user-avatar="user?.avatarUrl"
            @logout="handleLogout"
          />
        </nav>
      </div>
    </div>
  </header>
</template>
