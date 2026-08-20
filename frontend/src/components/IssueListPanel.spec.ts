import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import IssueListPanel from './IssueListPanel.vue'
import type { Issue } from '../contracts/inspection'

const issues: Issue[] = [
  {
    field: 'description',
    issue_type: '功效宣称风险',
    risk_level: 'high',
    evidence_span: '清热解毒',
    evidence: '清热解毒',
    rule_ids: ['food-health-001'],
    source: ['deterministic'],
    confidence: 0.9,
    suggestion: '改为描述口感或冲泡方式。',
  },
  {
    field: 'marketing_description',
    issue_type: '绝对化表达',
    risk_level: 'medium',
    evidence_span: '零添加',
    evidence: '零添加',
    rule_ids: ['food-copy-002'],
    source: ['deterministic'],
    confidence: 0.8,
    suggestion: '补充必要条件或调整表达。',
  },
]

describe('IssueListPanel', () => {
  it('filters to high-risk issues and emits the original issue index on selection', async () => {
    const wrapper = mount(IssueListPanel, {
      props: { issues, selectedIndex: null },
    })

    await wrapper.get('[data-testid="filter-high"]').trigger('click')

    expect(wrapper.findAll('[data-testid^="issue-card-"]')).toHaveLength(1)
    await wrapper.get('[data-testid="issue-card-1"]').trigger('click')
    expect(wrapper.emitted('select')?.[0]).toEqual([0])
  })
})
