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
})
