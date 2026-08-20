import { createPinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { InspectionReport } from '../contracts/inspection'

const apiMock = vi.hoisted(() => ({
  submitWorkbenchInspection: vi.fn(),
  getInspection: vi.fn(),
  getResult: vi.fn(),
  getRuleEvidence: vi.fn(),
  getTrace: vi.fn(),
  requestOptimization: vi.fn(),
}))

vi.mock('../api/inspections', () => ({ api: apiMock }))

import InspectionWorkbenchView from './InspectionWorkbenchView.vue'

const report: InspectionReport = {
  task_id: 'task-e2e-1',
  status: 'success',
  automated_risk_level: 'high',
  review_required: true,
  review_reasons: ['high_risk_issue'],
  issues: [
    {
      field: 'title',
      issue_type: '风险表达',
      risk_level: 'high',
      evidence_span: '风险词',
      evidence: '风险词',
      rule_ids: ['food-copy-001'],
      source: ['deterministic'],
      confidence: 1,
      suggestion: '使用客观产品描述。',
    },
    {
      field: 'description',
      issue_type: '描述一致性风险',
      risk_level: 'medium',
      evidence_span: '食品详情',
      evidence: '食品详情',
      rule_ids: ['food-copy-002'],
      source: ['deterministic'],
      confidence: 1,
      suggestion: '补充客观且一致的信息。',
    },
  ],
  degradation_flags: [],
  trace_id: 'trace-e2e-1',
}

function mountWorkbench() {
  return mount(InspectionWorkbenchView, {
    global: { plugins: [createPinia()] },
  })
}

async function fillRequiredFoodFields(wrapper: ReturnType<typeof mountWorkbench>): Promise<void> {
  await wrapper.get('input[name="title"]').setValue('食品风险词示例')
  await wrapper.get('textarea[name="selling-points"]').setValue('食品卖点')
  await wrapper.get('textarea[name="description"]').setValue('食品详情')
  await wrapper.get('textarea[name="marketing-description"]').setValue('食品营销描述')

  const attributesTab = wrapper
    .findAll('[role="tab"]')
    .find((tab) => tab.text().trim() === '食品属性')
  if (attributesTab === undefined) {
    throw new Error('未找到食品属性标签页')
  }
  await attributesTab.trigger('click')
  await wrapper.get('input[name="ingredients"]').setValue('原料')
  await wrapper.get('input[name="shelf-life"]').setValue('12个月')
  await wrapper.get('input[name="storage-method"]').setValue('阴凉干燥处保存')
  await wrapper.get('input[name="origin"]').setValue('中国')
}

describe('InspectionWorkbenchView end-to-end flow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiMock.submitWorkbenchInspection.mockResolvedValue({
      task_id: 'task-e2e-1',
      status: 'success',
      result_url: '/api/v2/inspections/task-e2e-1/result',
    })
    apiMock.getInspection.mockResolvedValue({
      task_id: 'task-e2e-1',
      status: 'success',
      trigger_source: 'vue_workbench',
      rule_version: 'food-v1',
    })
    apiMock.getResult.mockResolvedValue(report)
    apiMock.getRuleEvidence.mockResolvedValue({
      task_id: 'task-e2e-1',
      rules: [
        {
          rule_id: 'food-copy-001',
          version: '1.0.0',
          field_scope: ['title'],
          risk_level: 'high',
          rule_text: '项目方提供的规则文本。',
          rewrite_hint: '使用客观产品描述。',
        },
        {
          rule_id: 'food-copy-002',
          version: '1.0.0',
          field_scope: ['description'],
          risk_level: 'medium',
          rule_text: '项目方提供的第二条规则文本。',
          rewrite_hint: '补充客观且一致的信息。',
        },
      ],
    })
    apiMock.getTrace.mockResolvedValue({
      task_id: 'task-e2e-1',
      events: [],
    })
    apiMock.requestOptimization.mockResolvedValue({
      optimization_id: 'optimization-e2e-1',
      source_task_id: 'task-e2e-1',
      status: 'success',
      requested_fields: ['title'],
      optimized_fields: { title: '食品标题优化建议' },
      referenced_issues: [],
      referenced_rule_ids: ['food-copy-001'],
      verification_report: report,
      failure_reason: null,
    })
  })

  it('submits food copy, selects an issue, reads rule evidence, and explicitly requests optimization', async () => {
    const wrapper = mountWorkbench()
    await fillRequiredFoodFields(wrapper)

    const submitButton = wrapper.get('[data-testid="submit-inspection"]')
    expect(submitButton.attributes('disabled')).toBeUndefined()
    const nativeSubmitButton = submitButton.element as HTMLButtonElement
    const form = wrapper.get('form').element as HTMLFormElement
    form.requestSubmit(nativeSubmitButton)
    await flushPromises()

    expect(apiMock.submitWorkbenchInspection).toHaveBeenCalledWith(
      expect.objectContaining({
        category: '食品',
        title: '食品风险词示例',
        selling_points: ['食品卖点'],
        description: '食品详情',
        marketing_description: '食品营销描述',
        attributes: expect.objectContaining({
          ingredients: '原料',
          shelf_life: '12个月',
          storage_method: '阴凉干燥处保存',
          origin: '中国',
        }),
      }),
      false,
    )
    expect(wrapper.get('[data-testid="rule-evidence"]').text()).toContain('food-copy-001')
    await wrapper.get('[data-testid="issue-card-2"]').trigger('click')
    const selectedRule = wrapper.get('[data-testid="rule-evidence"]').text()
    expect(selectedRule).toContain('food-copy-002')
    expect(selectedRule).not.toContain('food-copy-001')

    expect(apiMock.requestOptimization).not.toHaveBeenCalled()
    await wrapper.get('[data-testid="optimize-title"]').setValue(true)
    await wrapper.get('[data-testid="request-optimization"]').trigger('click')
    await flushPromises()

    expect(apiMock.requestOptimization).toHaveBeenCalledWith('task-e2e-1', ['title'])
    expect(wrapper.get('[data-testid="optimization-status"] strong').text()).toBe('优化后验证通过')
  })

  it('uses native interactive controls with textual risk state for keyboard-accessible operation', async () => {
    const wrapper = mountWorkbench()
    await fillRequiredFoodFields(wrapper)
    const submitButton = wrapper.get('[data-testid="submit-inspection"]')
    expect(submitButton.attributes('disabled')).toBeUndefined()
    const nativeSubmitButton = submitButton.element as HTMLButtonElement
    const form = wrapper.get('form').element as HTMLFormElement
    form.requestSubmit(nativeSubmitButton)
    await flushPromises()

    const issueCard = wrapper.get('[data-testid="issue-card-1"]')
    expect(issueCard.element.tagName).toBe('BUTTON')
    expect(issueCard.attributes('type')).toBe('button')
    expect(issueCard.text()).toContain('高风险')

    const optimizationField = wrapper.get('[data-testid="optimize-title"]')
    expect(optimizationField.attributes('type')).toBe('checkbox')
  })
})
