import { describe, expect, it } from 'vitest'
import {
  pickDefaultModelId,
  resolveSelectedModelId,
} from '@/modules/workspace/composables/useWorkspaceModels'
import type { IAiModel } from '@/modules/workspace/types/workspaceConfig'

const claude: IAiModel = {
  id: 'anthropic/claude-sonnet-5',
  name: 'Claude Sonnet 5',
  provider: 'Anthropic',
  context_length: 1_000_000,
  cost_per_1m_input: 2,
  cost_per_1m_output: 10,
  tier: 'frontier',
  supports_vision: true,
  supports_tools: true,
  supports_reasoning: true,
  recommended: true,
}

const qwen: IAiModel = {
  id: 'qwen/qwen3.7-plus',
  name: 'Qwen3.7 Plus',
  provider: 'Qwen',
  context_length: 262_144,
  cost_per_1m_input: 0.4,
  cost_per_1m_output: 1.2,
  tier: 'balanced',
  supports_vision: false,
  supports_tools: true,
  supports_reasoning: true,
  recommended: false,
}

const models = [claude, qwen]

describe('pickDefaultModelId', () => {
  it('prefers the persisted default when it is in the catalog', () => {
    expect(pickDefaultModelId(models, qwen.id)).toBe(qwen.id)
  })

  it('falls back to recommended when default is missing', () => {
    expect(pickDefaultModelId(models, null)).toBe(claude.id)
  })
})

describe('resolveSelectedModelId', () => {
  it('does not provisional-pick recommended before config is fetched', () => {
    expect(
      resolveSelectedModelId({
        models,
        defaultModel: undefined,
        configFetched: false,
        currentSelectedId: null,
      }),
    ).toBeNull()
  })

  it('applies the saved default once config arrives (refresh race)', () => {
    // Catalog arrived first and would have pinned Claude — config then lands.
    expect(
      resolveSelectedModelId({
        models,
        defaultModel: qwen.id,
        configFetched: true,
        currentSelectedId: claude.id,
      }),
    ).toBe(qwen.id)
  })

  it('keeps a valid selection when no saved default is present', () => {
    expect(
      resolveSelectedModelId({
        models,
        defaultModel: null,
        configFetched: true,
        currentSelectedId: qwen.id,
      }),
    ).toBe(qwen.id)
  })

  it('falls back to recommended when saved default is not in the catalog', () => {
    expect(
      resolveSelectedModelId({
        models,
        defaultModel: 'missing/model',
        configFetched: true,
        currentSelectedId: null,
      }),
    ).toBe(claude.id)
  })
})
