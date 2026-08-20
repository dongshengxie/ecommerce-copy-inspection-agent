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
  issues: [],
  degradation_flags: [],
  trace_id: 'trace-1',
}

describe('workbench store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    apiMock.submitWorkbenchInspection.mockResolvedValue({
      task_id: 'task-1',
      status: 'success',
      result_url: '/api/v2/inspections/task-1/result',
    })
    apiMock.getInspection.mockResolvedValue({
      task_id: 'task-1',
      status: 'success',
      trigger_source: 'vue_workbench',
      rule_version: 'food-v1',
    })
    apiMock.getResult.mockResolvedValue(report)
    apiMock.getRuleEvidence.mockResolvedValue({ task_id: 'task-1', rules: [] })
    apiMock.getTrace.mockResolvedValue({ task_id: 'task-1', events: [] })
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
})
