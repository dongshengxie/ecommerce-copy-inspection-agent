import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { InspectionReport } from '../contracts/inspection'
import { ApiClientError } from '../api/client'

const apiMock = vi.hoisted(() => ({
  submitWorkbenchInspection: vi.fn(),
  getInspection: vi.fn(),
  getResult: vi.fn(),
  getRuleEvidence: vi.fn(),
  getTrace: vi.fn(),
  requestOptimization: vi.fn(),
}))

vi.mock('../api/inspections', () => ({ api: apiMock }))

import { useWorkbenchStore, type FoodCopyForm } from './workbench'

const foodForm: FoodCopyForm = {
  title: '茉莉花茶袋泡茶 30g',
  sellingPointsText: '茶香清雅\n\n独立袋泡',
  description: '精选茉莉花与绿茶窨制而成。',
  attributes: {
    ingredients: '绿茶、茉莉花',
    shelf_life: '18个月',
    storage_method: '阴凉干燥处保存',
    origin: '福建',
  },
  marketing_description: '日常饮用的袋泡茶。',
}

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

describe('workbench store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    apiMock.submitWorkbenchInspection.mockImplementation(async () => ({
      task_id: `task-${apiMock.submitWorkbenchInspection.mock.calls.length}`,
      status: 'success',
      result_url: '/api/v2/inspections/task/result',
    }))
    apiMock.getInspection.mockImplementation(async (taskId: string) => ({
      task_id: taskId,
      status: 'success',
      trigger_source: 'vue_workbench',
      rule_version: 'food-v1',
    }))
    apiMock.getResult.mockImplementation(async (taskId: string) => ({ ...report, task_id: taskId }))
    apiMock.getRuleEvidence.mockImplementation(async (taskId: string) => ({ task_id: taskId, rules: [] }))
    apiMock.getTrace.mockImplementation(async (taskId: string) => ({ task_id: taskId, events: [] }))
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
  })

  it('keeps the submitted copy in memory while loading its inspection report', async () => {
    const store = useWorkbenchStore()

    await store.submit(foodForm, false)

    expect(apiMock.submitWorkbenchInspection).toHaveBeenCalledWith(
      expect.objectContaining({
        category: '食品',
        selling_points: ['茶香清雅', '独立袋泡'],
      }),
      false,
    )
    expect(store.submittedCopy?.title).toBe(foodForm.title)
    expect(store.phase).toBe('completed')
    expect(store.report).toEqual(report)
  })

  it('keeps submitted copy and exposes only a safe error when inspection fails', async () => {
    apiMock.submitWorkbenchInspection.mockRejectedValueOnce(new ApiClientError('network', true))
    const store = useWorkbenchStore()

    await store.submit(foodForm, true)

    expect(store.submittedCopy?.description).toBe(foodForm.description)
    expect(store.phase).toBe('failed')
    expect(store.errorMessage).toBe('网络连接异常或请求超时，请稍后重试。')
  })

  it('requests optimization only after an inspection task exists', async () => {
    const store = useWorkbenchStore()
    await store.submit(foodForm, false)

    await store.requestOptimization('task-1', ['title'])

    expect(apiMock.requestOptimization).toHaveBeenCalledWith('task-1', ['title'])
    expect(store.optimization?.status).toBe('success')
  })

  it('rejects optimization requests that do not match the active task and reported fields', async () => {
    const store = useWorkbenchStore()
    await store.submit(foodForm, false)

    await store.requestOptimization('task-other', ['title'])
    await store.requestOptimization('task-1', ['marketing_description'])

    expect(apiMock.requestOptimization).not.toHaveBeenCalled()
    expect(store.optimization).toBeNull()
  })

  it('ignores an optimization response that becomes stale after a new inspection submission', async () => {
    const store = useWorkbenchStore()
    await store.submit(foodForm, false)

    let resolveOptimization: ((value: unknown) => void) | undefined
    apiMock.requestOptimization.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveOptimization = resolve
        }),
    )

    const staleRequest = store.requestOptimization('task-1', ['title'])
    await store.submit(foodForm, false)
    resolveOptimization?.({
      optimization_id: 'optimization-stale',
      source_task_id: 'task-1',
      status: 'success',
      requested_fields: ['title'],
      optimized_fields: { title: '旧任务文案' },
      referenced_issues: [],
      referenced_rule_ids: [],
      verification_report: report,
      failure_reason: null,
    })
    await staleRequest

    expect(store.task?.task_id).toBe('task-2')
    expect(store.optimization).toBeNull()
    expect(store.optimizing).toBe(false)
  })

  it('rejects an optimization response that does not belong to the submitted task and fields', async () => {
    apiMock.requestOptimization.mockResolvedValueOnce({
      optimization_id: 'optimization-mismatched',
      source_task_id: 'task-other',
      status: 'success',
      requested_fields: ['description'],
      optimized_fields: { description: '不应展示的文案' },
      referenced_issues: [],
      referenced_rule_ids: [],
      verification_report: report,
      failure_reason: null,
    })
    const store = useWorkbenchStore()
    await store.submit(foodForm, false)

    await store.requestOptimization('task-1', ['title'])

    expect(store.optimization).toBeNull()
    expect(store.optimizationErrorMessage).toBe('服务返回结果异常，请稍后重试。')
  })

  it('rejects a response whose requested fields contain duplicates instead of the submitted set', async () => {
    apiMock.requestOptimization.mockResolvedValueOnce({
      optimization_id: 'optimization-duplicate-fields',
      source_task_id: 'task-1',
      status: 'success',
      requested_fields: ['title', 'title'],
      optimized_fields: { title: '不应展示的文案' },
      referenced_issues: [],
      referenced_rule_ids: [],
      verification_report: report,
      failure_reason: null,
    })
    const store = useWorkbenchStore()
    await store.submit(foodForm, false)

    await store.requestOptimization('task-1', ['title', 'description'])

    expect(store.optimization).toBeNull()
    expect(store.optimizationErrorMessage).toBe('服务返回结果异常，请稍后重试。')
  })
})
