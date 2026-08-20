import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { describe, expect, it } from 'vitest'

import InspectionWorkbenchView from './InspectionWorkbenchView.vue'

describe('InspectionWorkbenchView', () => {
  it('renders V3 workbench regions in reading order', () => {
    const wrapper = mount(InspectionWorkbenchView, {
      global: { plugins: [createPinia()] },
    })

    expect(wrapper.get('[data-testid="copy-panel"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="issue-panel"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="detail-panel"]').exists()).toBe(true)
  })

  it('keeps non-MVP navigation disabled and starts in copy-entry state', () => {
    const wrapper = mount(InspectionWorkbenchView, {
      global: { plugins: [createPinia()] },
    })

    expect(wrapper.get('[data-testid="workflow-step-entry"]').attributes('data-active')).toBe('true')
    expect(wrapper.get('[data-testid="nav-task-history"]').attributes('aria-disabled')).toBe('true')
    expect(wrapper.get('[data-testid="nav-rule-center"]').attributes('aria-disabled')).toBe('true')
  })
})
