import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from './inspections'

const foodSubmission = {
  category: '食品' as const,
  title: '茉莉花茶袋泡茶 30g',
  selling_points: ['茶香清雅'],
  description: '精选茉莉花与绿茶窨制而成。',
  attributes: {
    ingredients: '绿茶、茉莉花',
    shelf_life: '18个月',
    storage_method: '阴凉干燥处保存',
    origin: '福建',
  },
  marketing_description: '日常饮用的袋泡茶。',
}

describe('inspection API', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('does not retry a timed-out submission automatically', async () => {
    const mockedFetch = vi.fn().mockRejectedValueOnce(new DOMException('timeout', 'AbortError'))
    vi.stubGlobal('fetch', mockedFetch)

    await expect(api.submitWorkbenchInspection(foodSubmission, false)).rejects.toMatchObject({
      kind: 'network',
      retryableByUser: true,
    })

    expect(mockedFetch).toHaveBeenCalledTimes(1)
  })

  it('retries a failed task lookup once before returning its typed response', async () => {
    const mockedFetch = vi
      .fn()
      .mockRejectedValueOnce(new TypeError('network unavailable'))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            task_id: 'task-1',
            status: 'success',
            trigger_source: 'vue_workbench',
            rule_version: 'food-v1',
          }),
          { status: 200, headers: { 'content-type': 'application/json' } },
        ),
      )
    vi.stubGlobal('fetch', mockedFetch)

    await expect(api.getInspection('task-1')).resolves.toMatchObject({
      task_id: 'task-1',
      rule_version: 'food-v1',
    })
    expect(mockedFetch).toHaveBeenCalledTimes(2)
  })

  it('retries a transient server failure for a GET request once', async () => {
    const mockedFetch = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 503 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            task_id: 'task-1',
            status: 'success',
            trigger_source: 'vue_workbench',
            rule_version: 'food-v1',
          }),
          { status: 200, headers: { 'content-type': 'application/json' } },
        ),
      )
    vi.stubGlobal('fetch', mockedFetch)

    await expect(api.getInspection('task-1')).resolves.toMatchObject({ task_id: 'task-1' })
    expect(mockedFetch).toHaveBeenCalledTimes(2)
  })

  it('encodes task identifiers and sends only requested fields for optimization', async () => {
    const mockedFetch = vi.fn().mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          optimization_id: 'optimization-1',
          source_task_id: 'task / 1',
          status: 'success',
          requested_fields: ['description'],
          optimized_fields: { description: '建议文案' },
          referenced_issues: [],
          referenced_rule_ids: [],
          verification_report: null,
          failure_reason: null,
        }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      ),
    )
    vi.stubGlobal('fetch', mockedFetch)

    await api.requestOptimization('task / 1', ['description'])

    expect(mockedFetch).toHaveBeenCalledWith(
      '/api/v2/inspections/task%20%2F%201/optimization',
      expect.objectContaining({ body: JSON.stringify({ fields: ['description'] }), method: 'POST' }),
    )
  })

  it('does not expose an invalid response body to the caller', async () => {
    const mockedFetch = vi
      .fn()
      .mockResolvedValueOnce(new Response('unexpected response', { status: 200 }))
    vi.stubGlobal('fetch', mockedFetch)

    await expect(api.getResult('task-1')).rejects.toMatchObject({
      kind: 'invalid_response',
      retryableByUser: false,
    })
  })

  it('rejects an object that does not satisfy the inspection report contract', async () => {
    const mockedFetch = vi.fn().mockResolvedValueOnce(
      new Response(JSON.stringify({ task_id: 'task-1' }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', mockedFetch)

    await expect(api.getResult('task-1')).rejects.toMatchObject({
      kind: 'invalid_response',
      retryableByUser: false,
    })
  })
})
