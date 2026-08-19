import type { WritableCopyField } from '../contracts/inspection'

interface EnabledCategoryCapability {
  label: string
  enabled: true
  writableFields: readonly WritableCopyField[]
}

interface DisabledCategoryCapability {
  label: string
  enabled: false
}

export const categoryCapabilities = {
  food: {
    label: '食品',
    enabled: true,
    writableFields: ['title', 'selling_points', 'description', 'marketing_description'],
  },
  beauty: { label: '美妆', enabled: false },
  homeAppliance: { label: '家电', enabled: false },
} as const satisfies Record<string, EnabledCategoryCapability | DisabledCategoryCapability>

export type CategoryKey = keyof typeof categoryCapabilities

export function getSubmissionCapability(category: CategoryKey): EnabledCategoryCapability | undefined {
  const capability = categoryCapabilities[category]
  return capability.enabled ? capability : undefined
}
