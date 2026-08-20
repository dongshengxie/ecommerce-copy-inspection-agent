import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import TraceSummary from './TraceSummary.vue'

describe('TraceSummary', () => {
  it('does not report complete success when a trace step has failed', () => {
    const wrapper = mount(TraceSummary, {
      props: {
        trace: {
          task_id: 'task-1',
          events: [
            {
              step_name: 'food_quality',
              tool_or_skill_name: 'food_quality_skill',
              rule_ids: ['food-copy-001'],
              decision: '发现风险表达',
              status: 'failed',
              latency_ms: 320,
              metadata: { operation: 'inspection' },
            },
          ],
        },
        degradationFlags: [],
      },
    })

    expect(wrapper.get('[data-testid="trace-summary"]').text()).toContain('含失败或降级')
    expect(wrapper.get('[data-testid="trace-summary"]').text()).not.toContain('全部成功')
  })

  it('does not report complete success when the report contains degradation flags', () => {
    const wrapper = mount(TraceSummary, {
      props: {
        trace: {
          task_id: 'task-1',
          events: [
            {
              step_name: 'food_quality',
              tool_or_skill_name: 'food_quality_skill',
              rule_ids: [],
              decision: '完成检查',
              status: 'success',
              latency_ms: 320,
              metadata: {},
            },
          ],
        },
        degradationFlags: ['semantic_inspection_unavailable'],
      },
    })

    expect(wrapper.get('[data-testid="trace-summary"]').text()).toContain('含失败或降级')
    expect(wrapper.get('[data-testid="trace-summary"]').text()).not.toContain('全部成功')
  })
})
