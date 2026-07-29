/**
 * TypeScript types for Stripe billing module
 */

export type PlanTier = 'free' | 'pro' | 'pro_plus'

export type BillingInterval = 'monthly' | 'annual'

export type SubscriptionStatus = 'active' | 'canceled' | 'past_due' | 'unpaid' | 'incomplete'

export interface Subscription {
  id: string
  userId: string
  stripeCustomerId: string | null
  stripeSubscriptionId: string | null
  planTier: PlanTier
  billingInterval: BillingInterval | null
  status: SubscriptionStatus
  currentPeriodStart: string | null
  currentPeriodEnd: string | null
  cancelAtPeriodEnd: boolean
  isGrandfathered: boolean
  createdAt: string
  updatedAt: string
}

export interface SubscriptionLimits {
  planTier: PlanTier
  aiMonthlyTokenLimit: number
  storageLimit: number
  canExportData: boolean
  canUseAdvancedFeatures: boolean
  requiresByok: boolean
  workspaceMonthlyIncludedUsd?: number | null
  workspaceUsedUsd?: number | null
  workspacePeriodStart?: string | null
  workspacePeriodEnd?: string | null
  webSearchUsed?: number | null
  webSearchCap?: number | null
}

export interface CreateCheckoutSessionRequest {
  planTier: Exclude<PlanTier, 'free'>
  billingInterval: BillingInterval
  successUrl: string
  cancelUrl: string
}

export interface CheckoutSessionResponse {
  sessionId: string
  sessionUrl: string
}

export interface CreatePortalSessionRequest {
  returnUrl: string
}

export interface PortalSessionResponse {
  sessionUrl: string
}

export interface UpdateOpenRouterTokenRequest {
  openrouterApiToken: string | null
}

export interface PlanFeatures {
  tier: PlanTier
  name: string
  price: {
    monthly: number
    annual: number
    annualMonthly: number // Annual price divided by 12
  }
  features: string[]
  limits: {
    aiTokens: number
    storage: number
    items: number
    containers: number
  }
  popular?: boolean
}

export const PLAN_FEATURES: Record<PlanTier, PlanFeatures> = {
  free: {
    tier: 'free',
    name: 'Free',
    price: {
      monthly: 0,
      annual: 0,
      annualMonthly: 0,
    },
    features: [
      'Basic gear management',
      'Data export (JSON/Markdown)',
      'BYOK: Bring Your Own API Key (OpenRouter)',
      '100 MB storage',
      '2,000 items limit',
      '100 containers limit',
    ],
    limits: {
      aiTokens: 0, // BYOK required
      storage: 100 * 1024 * 1024, // 100 MB
      items: 2000,
      containers: 100,
    },
  },
  pro: {
    tier: 'pro',
    name: 'Pro',
    price: {
      monthly: 5.0,
      annual: 50,
      annualMonthly: 4.17,
    },
    features: [
      'Everything in Free',
      'AI-powered gear recommendations',
      '~$1 worth of AI tokens/month',
      'Advanced features',
      '5 GB storage',
      '10,000 items limit',
      '250 containers limit',
    ],
    limits: {
      aiTokens: 1_000_000,
      storage: 5 * 1024 * 1024 * 1024, // 5 GB
      items: 10000,
      containers: 250,
    },
    popular: true,
  },
  pro_plus: {
    tier: 'pro_plus',
    name: 'Pro Plus',
    price: {
      monthly: 15.0,
      annual: 150,
      annualMonthly: 12.5,
    },
    features: [
      'Everything in Pro',
      'Priority AI processing',
      '~$10 worth of AI tokens/month',
      'Premium support',
      '50 GB storage',
      '50,000 items limit',
      '500 containers limit',
    ],
    limits: {
      aiTokens: 10_000_000,
      storage: 50 * 1024 * 1024 * 1024, // 50 GB
      items: 50000,
      containers: 500,
    },
  },
}

export const ANNUAL_DISCOUNT_PERCENT = 17
