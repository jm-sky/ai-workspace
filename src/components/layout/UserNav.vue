<script setup lang="ts">
import { CreditCard, Link2, LogIn, LogOut, SettingsIcon, ShieldIcon, UserIcon, UserPlusIcon } from 'lucide-vue-next'
import { type Component, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { cn } from '@/lib/utils'
import { AdminRoutePaths } from '@/modules/admin/routes'
import { useAuth } from '@/modules/auth/composables/useAuth'
import { AuthRoutePaths } from '@/modules/auth/config/routes'
import { BillingRoutePaths } from '@/modules/billing/routes'
import { SettingsRoutePaths } from '@/modules/settings/routes'
import { UserRoutePaths } from '@/modules/user/routes'
import { generateGravatarUrl, GRAVATAR_BASE_URL } from '@/modules/user/utils/generateGravatarUrl'
import { usePermissions } from '@/shared/composables/usePermissions'
import { getInitials } from '@/shared/utils/getInitials'
import Avatar from '../ui/avatar/Avatar.vue'
import AvatarFallback from '../ui/avatar/AvatarFallback.vue'
import AvatarImage from '../ui/avatar/AvatarImage.vue'
import DropdownMenuItemLink from '../ui/dropdown-menu/DropdownMenuItemLink.vue'

const AVATAR_SIZE = 32

export interface Link {
  to: string
  label: string
  icon?: Component
  disabled?: boolean
  hidden?: boolean
}

export interface UserNavProps {
  userName?: string
  userEmail?: string
  userAvatar?: string
  coreLinks?: Link[]
  navLinks?: Link[]
}

const { t } = useI18n()
const { isAuthenticated } = useAuth()
const { canAccessAdminPanel } = usePermissions()

const props = defineProps<UserNavProps>()

const emit = defineEmits<{
  logout: []
}>()

const defaultCoreLinks = computed<Link[]>(() => [
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
  }
])

const coreLinksList = computed<Link[]>(() => props.coreLinks ?? defaultCoreLinks.value)
const coreLinksFiltered = computed<Link[]>(() => coreLinksList.value.filter((link) => !link.hidden))
const initials = computed<string>(() => getInitials(props.userName ?? props.userEmail ?? 'U'))

const avatarUrl = computed<string | undefined>(() =>{
  if (props.userAvatar?.startsWith(GRAVATAR_BASE_URL)) {
    return props.userAvatar.replace(/&s=\d+/, `&s=${AVATAR_SIZE}`)
  }

  if (!props.userAvatar && props.userEmail) {
    return generateGravatarUrl(props.userEmail, AVATAR_SIZE)
  }

  return props.userAvatar
})

const handleLogout = () => {
  emit('logout')
}
</script>

<template>
  <DropdownMenu>
    <DropdownMenuTrigger as-child>
      <Avatar
        role="button"
        :aria-label="t('user.menu.title', 'User menu')"
        :class="cn('ml-2 cursor-pointer hover:brightness-95 transition-all duration-300', !isAuthenticated && 'ring-2 ring-muted-foreground/30', isAuthenticated && canAccessAdminPanel && 'ring-2 ring-primary ring-offset-2 ring-offset-background')"
      >
        <AvatarImage
          :src="avatarUrl ?? ''"
          :alt="isAuthenticated ? (userName ?? userEmail ?? t('user.avatar.alt', 'User avatar')) : t('user.avatar.guestAlt', 'Guest avatar')"
        />
        <AvatarFallback :class="isAuthenticated ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'">
          <UserIcon v-if="!isAuthenticated" class="size-4" />
          <template v-else>
            {{ initials }}
          </template>
        </AvatarFallback>
      </Avatar>
    </DropdownMenuTrigger>

    <DropdownMenuContent class="w-64" align="end">
      <!-- User info -->
      <DropdownMenuLabel v-if="isAuthenticated">
        <div class="flex flex-col space-y-1">
          <p class="text-sm font-medium leading-none">
            {{ userName ?? 'N/A' }}
          </p>
          <p class="text-xs leading-none text-muted-foreground">
            {{ userEmail ?? '-' }}
          </p>
        </div>
      </DropdownMenuLabel>
      <DropdownMenuLabel v-else>
        <div class="flex flex-col space-y-1">
          <p class="text-sm font-medium leading-none">
            {{ t('user.guest', 'Guest') }}
          </p>
        </div>
      </DropdownMenuLabel>

      <DropdownMenuSeparator />

      <!-- Navigation Links (mobile only) -->
      <template v-if="navLinks && navLinks.length > 0">
        <div class="md:hidden">
          <DropdownMenuItemLink
            v-for="link in navLinks"
            :key="link.to"
            :to="link.to"
          >
            <component :is="link.icon" v-if="link.icon" class="size-4 mr-2" />
            {{ link.label }}
          </DropdownMenuItemLink>
          <DropdownMenuSeparator />
        </div>
      </template>

      <!-- Profile/Settings slot -->
      <slot name="menu-items">
        <DropdownMenuItemLink
          v-for="link in coreLinksFiltered"
          v-show="!link.hidden"
          :key="link.to"
          :to="link.to"
        >
          <component :is="link.icon" v-if="link.icon" class="size-4 mr-2" />
          {{ link.label }}
        </DropdownMenuItemLink>
      </slot>

      <DropdownMenuSeparator />

      <!-- Logout -->
      <DropdownMenuItem v-if="isAuthenticated" @click="handleLogout">
        <LogOut class="size-4 mr-2" />
        {{ t('auth.logout', 'Logout') }}
      </DropdownMenuItem>
      <template v-else>
        <DropdownMenuItemLink :to="AuthRoutePaths.login">
          <LogIn class="size-4 mr-2" />
          {{ t('auth.login', 'Login') }}
        </DropdownMenuItemLink>
        <DropdownMenuItemLink :to="AuthRoutePaths.register">
          <UserPlusIcon class="size-4 mr-2" />
          {{ t('auth.register', 'Register') }}
        </DropdownMenuItemLink>
      </template>
    </DropdownMenuContent>
  </DropdownMenu>
</template>
