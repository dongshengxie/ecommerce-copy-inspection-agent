import { createPinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { InspectionReport } from '../contracts/inspection'
import { useWorkbenchStore } from '../stores/workbench'

const apiMock = vi.hoisted(() => ({ requestOptimization: vi.fn() }))

vi.mock('../api/inspections', () => ({ api: apiMock }))

import OptimizationPanel from './OptimizationPanel.vue'

const report: InspectionReport = {
  task_id: 'task-1',
  status: 'success',
  automated_risk_level: 'medium',
  review_required: false,
  review_reasons: [],
  issues: [
    {
      field: 'title',
      issue_type: '绝对化表达',
      risk_level: 'medium',
      evidence_span: '最佳',
      evidence: '最佳',
      rule_ids: ['food-copy-001'],
      source: ['deterministic'],
      confidence: 0.8,
      suggestion: '调整为可验证的产品描述。',
    },
    {
      field: 'description',
      issue_type: '绝对化表达',
      risk_level: 'medium',
      evidence_span: '最佳',
      evidence: '最佳',
      rule_ids: ['food-copy-001'],
      source: ['deterministic'],
      confidence: 0.8,
      suggestion: '调整为可验证的产品描述。',
    },
  ],
  degradation_flags: [],
  trace_id: 'trace-1',
}

function mountPanel() {
  const pinia = createPinia()
  const store = useWorkbenchStore(pinia)
  store.phase = 'completed'
  store.task = {
    task_id: 'task-1',
    status: 'success',
    trigger_source: 'vue_workbench',
    rule_version: 'food-v1',
  }
  store.report = report

  return mount(OptimizationPanel, {
    props: { taskId: 'task-1', report },
    global: { plugins: [pinia] },
  })
}

describe('OptimizationPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('does not call optimization until the user selects a writable field and confirms', async () => {
    apiMock.requestOptimization.mockResolvedValue({
      optimization_id: 'optimization-1',
      source_task_id: 'task-1',
      status: 'success',
      requested_fields: ['title'],
      optimized_fields: { title: '茉莉花茶袋泡茶' },
      referenced_issues: [],
      referenced_rule_ids: [],
      verification_report: report,
      failure_reason: null,
    })
    const wrapper = mountPanel()

    expect(apiMock.requestOptimization).not.toHaveBeenCalled()
    await wrapper.get('[data-testid="optimize-title"]').setValue(true)
    await wrapper.get('[data-testid="request-optimization"]').trigger('click')
    await flushPromises()

    expect(apiMock.requestOptimization).toHaveBeenCalledWith('task-1', ['title'])
    expect(wrapper.get('[data-testid="optimization-status"] strong').text()).toBe('优化后验证通过')
  })

  it('shows the safe review message without exposing a failed verification reason', async () => {
    apiMock.requestOptimization.mockResolvedValue({
      optimization_id: 'optimization-2',
      source_task_id: 'task-1',
      status: 'verification_failed',
      requested_fields: ['title'],
      optimized_fields: { title: '茉莉花茶袋泡茶' },
      referenced_issues: [],
      referenced_rule_ids: [],
      verification_report: report,
      failure_reason: '模型返回了不应暴露的内部错误',
    })
    const wrapper = mountPanel()

    await wrapper.get('[data-testid="optimize-title"]').setValue(true)
    await wrapper.get('[data-testid="request-optimization"]').trigger('click')
    await flushPromises()

    const result = wrapper.get('[data-testid="optimization-status"]')
    expect(result.get('strong').text()).toBe('优化后验证未通过，建议人工复核')
    expect(result.text()).not.toContain('模型返回了不应暴露的内部错误')
  })

  it('shows the fixed failed message without exposing optimized text or a failure reason', async () => {
    apiMock.requestOptimization.mockResolvedValue({
      optimization_id: 'optimization-3',
      source_task_id: 'task-1',
      status: 'failed',
      requested_fields: ['title'],
      optimized_fields: { title: '不应展示的文案' },
      referenced_issues: [],
      referenced_rule_ids: [],
      verification_report: null,
      failure_reason: '不应展示的内部原因',
    })
    const wrapper = mountPanel()

    await wrapper.get('[data-testid="optimize-title"]').setValue(true)
    await wrapper.get('[data-testid="request-optimization"]').trigger('click')
    await flushPromises()

    const result = wrapper.get('[data-testid="optimization-status"]')
    expect(result.get('strong').text()).toBe('优化未完成，请稍后重试或人工处理')
    expect(result.text()).not.toContain('不应展示的文案')
    expect(result.text()).not.toContain('不应展示的内部原因')
  })

  it('freezes the request field selection while optimization is pending and hides extra returned fields', async () => {
    let resolveOptimization: ((value: unknown) => void) | undefined
    apiMock.requestOptimization.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveOptimization = resolve
        }),
    )
    const wrapper = mountPanel()

    await wrapper.get('[data-testid="optimize-title"]').setValue(true)
    await wrapper.get('[data-testid="request-optimization"]').trigger('click')

    expect(wrapper.get('[data-testid="optimize-title"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="optimize-description"]').attributes('disabled')).toBeDefined()

    resolveOptimization?.({
      optimization_id: 'optimization-extra',
      source_task_id: 'task-1',
      status: 'success',
      requested_fields: ['title'],
      optimized_fields: {
        title: '标题优化结果',
        description: '不应展示的额外结果',
      },
      referenced_issues: [],
      referenced_rule_ids: [],
      verification_report: report,
      failure_reason: null,
    })
    await flushPromises()

    const result = wrapper.get('[data-testid="optimization-status"]').text()
    expect(result).toContain('标题优化结果')
    expect(result).not.toContain('不应展示的额外结果')
  })
})
