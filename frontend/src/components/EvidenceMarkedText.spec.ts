import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import EvidenceMarkedText from './EvidenceMarkedText.vue'

describe('EvidenceMarkedText', () => {
  it('marks every exact occurrence and anchors the issue number on the first match', () => {
    const wrapper = mount(EvidenceMarkedText, {
      props: { text: '清热解毒，清热解毒', evidence: '清热解毒', issueNumber: 1 },
    })

    expect(wrapper.findAll('[data-testid="evidence-highlight"]')).toHaveLength(2)
    expect(wrapper.findAll('[data-testid="issue-marker"]')).toHaveLength(1)
  })

  it('anchors every related issue number when distinct issues share one evidence span', () => {
    const wrapper = mount(EvidenceMarkedText, {
      props: {
        text: '清热解毒',
        matches: [
          { evidence: '清热解毒', issueNumber: 1 },
          { evidence: '清热解毒', issueNumber: 2 },
        ],
      },
    })

    expect(wrapper.findAll('[data-testid="evidence-highlight"]')).toHaveLength(1)
    expect(wrapper.findAll('[data-testid="issue-marker"]')).toHaveLength(2)
    expect(wrapper.findAll('[data-testid="issue-marker"]').map((marker) => marker.text())).toEqual([
      '1',
      '2',
    ])
  })

  it('keeps every issue marker when one evidence span contains another', () => {
    const wrapper = mount(EvidenceMarkedText, {
      props: {
        text: '这款茶可以改善睡眠，适合睡前饮用。',
        matches: [
          { evidence: '改善睡眠', issueNumber: 1, riskLevel: 'medium' },
          { evidence: '可以改善睡眠', issueNumber: 2, riskLevel: 'high' },
        ],
      },
    })

    expect(wrapper.findAll('[data-testid="evidence-highlight"]')).toHaveLength(1)
    expect(wrapper.find('[data-testid="evidence-highlight"]').classes()).toContain('risk-high')
    expect(wrapper.findAll('[data-testid="issue-marker"]').map((marker) => marker.text())).toEqual([
      '1',
      '2',
    ])
    expect(wrapper.findAll('[data-testid="issue-marker"]')[0].classes()).toContain('risk-medium')
    expect(wrapper.findAll('[data-testid="issue-marker"]')[1].classes()).toContain('risk-high')
  })
})
