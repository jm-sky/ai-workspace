<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import CommonPageHeader from '@/components/layout/CommonPageHeader.vue'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import AuthenticatedLayout from '@/layouts/AuthenticatedLayout.vue'
import type { BillingInterval } from '../types'
import PlanCard from '../components/PlanCard.vue'
import SubscriptionCard from '../components/SubscriptionCard.vue'
import WorkspaceUsageCard from '../components/WorkspaceUsageCard.vue'
import { useSubscription } from '../composables/useSubscription'
import { BillingRouteIcon } from '../routes'
import { PLAN_FEATURES } from '../types'

const { t } = useI18n()
const { currentPlan, upgradeToPlan, isUpgrading } = useSubscription()

const billingInterval = ref<BillingInterval>('monthly')

const handleSelectPlan = async (planTier: 'pro' | 'pro_plus') => {
  await upgradeToPlan(planTier, billingInterval.value)
}
</script>

<template>
  <AuthenticatedLayout>
    <div class="space-y-6 w-full max-w-full">
      <CommonPageHeader
        :icon="BillingRouteIcon.billing"
        :label="t('billing.title')"
        :description="t('billing.description')"
      />

      <div class="grid gap-8 lg:grid-cols-3">
        <div class="lg:col-span-1 space-y-6">
          <SubscriptionCard />
          <WorkspaceUsageCard />
        </div>

        <div class="lg:col-span-2">
          <div class="space-y-6">
            <div>
              <h2 class="text-2xl font-bold">
                {{ t('billing.upgradePlan') }}
              </h2>
              <p class="mt-2 text-muted-foreground">
                {{ t('billing.choosePlan') }}
              </p>
            </div>

            <Tabs :model-value="billingInterval" @update:model-value="(v) => billingInterval = v as BillingInterval">
              <TabsList class="grid w-full grid-cols-2">
                <TabsTrigger value="monthly">
                  {{ t('billing.monthly') }}
                </TabsTrigger>
                <TabsTrigger value="annual">
                  {{ t('billing.annual') }} ({{ t('billing.savePercent', { percent: 17 }) }})
                </TabsTrigger>
              </TabsList>

              <TabsContent value="monthly" class="mt-6">
                <div class="grid gap-6 md:grid-cols-2">
                  <PlanCard
                    :plan="PLAN_FEATURES.pro"
                    billing-interval="monthly"
                    :is-current-plan="currentPlan === 'pro'"
                    :is-loading="isUpgrading"
                    :on-select-plan="() => handleSelectPlan('pro')"
                  />
                  <PlanCard
                    :plan="PLAN_FEATURES.pro_plus"
                    billing-interval="monthly"
                    :is-current-plan="currentPlan === 'pro_plus'"
                    :is-loading="isUpgrading"
                    :on-select-plan="() => handleSelectPlan('pro_plus')"
                  />
                </div>
              </TabsContent>

              <TabsContent value="annual" class="mt-6">
                <div class="grid gap-6 md:grid-cols-2">
                  <PlanCard
                    :plan="PLAN_FEATURES.pro"
                    billing-interval="annual"
                    :is-current-plan="currentPlan === 'pro'"
                    :is-loading="isUpgrading"
                    :on-select-plan="() => handleSelectPlan('pro')"
                  />
                  <PlanCard
                    :plan="PLAN_FEATURES.pro_plus"
                    billing-interval="annual"
                    :is-current-plan="currentPlan === 'pro_plus'"
                    :is-loading="isUpgrading"
                    :on-select-plan="() => handleSelectPlan('pro_plus')"
                  />
                </div>
              </TabsContent>
            </Tabs>
          </div>
        </div>
      </div>
    </div>
  </AuthenticatedLayout>
</template>
