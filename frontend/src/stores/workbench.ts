import { ref } from 'vue'
import { defineStore } from 'pinia'

import { api } from '../api/inspections'
import { ApiClientError } from '../api/client'
import type {
  FoodAttributes,
  FoodWorkbenchSubmission,
  InspectionReport,
  InspectionTask,
  OptimizationResult,
  RuleEvidenceResponse,
  SafeTraceResponse,
  WritableCopyField,
} from '../contracts/inspection'

export type WorkbenchPhase = 'editing' | 'submitting' | 'loading_result' | 'completed' | 'failed'

export interface FoodCopyForm {
  title: string
  sellingPointsText: string
  description: string
  attributes: FoodAttributes
  marketing_description: string
}

export function createEmptyFoodCopyForm(): FoodCopyForm {
  return {
    title: '',
    sellingPointsText: '',
    description: '',
    attributes: {
      ingredients: '',
      shelf_life: '',
      storage_method: '',
      origin: '',
      applicable_people: '',
      net_content: '',
      brand: '',
    },
    marketing_description: '',
  }
}

export const useWorkbenchStore = defineStore('workbench', () => {
  const phase = ref<WorkbenchPhase>('editing')
  const submittedCopy = ref<FoodWorkbenchSubmission | null>(null)
  const task = ref<InspectionTask | null>(null)
  const report = ref<InspectionReport | null>(null)
  const ruleEvidence = ref<RuleEvidenceResponse | null>(null)
  const trace = ref<SafeTraceResponse | null>(null)
  const errorMessage = ref<string | null>(null)
  const optimization = ref<OptimizationResult | null>(null)
  const optimizing = ref(false)
  const optimizationErrorMessage = ref<string | null>(null)
  const optimizationRequestedFields = ref<WritableCopyField[]>([])
  let optimizationRequestGeneration = 0

  async function submit(form: FoodCopyForm, semanticEnabled: boolean): Promise<void> {
    if (phase.value === 'submitting' || phase.value === 'loading_result') {
      return
    }

    const copy = toFoodSubmission(form)
    submittedCopy.value = copy
    errorMessage.value = null
    task.value = null
    report.value = null
    ruleEvidence.value = null
    trace.value = null
    optimization.value = null
    optimizing.value = false
    optimizationErrorMessage.value = null
    optimizationRequestedFields.value = []
    optimizationRequestGeneration += 1
    phase.value = 'submitting'

    try {
      const created = await api.submitWorkbenchInspection(copy, semanticEnabled)
      phase.value = 'loading_result'
      task.value = await api.getInspection(created.task_id)
      report.value = await api.getResult(created.task_id)
      ruleEvidence.value = await api.getRuleEvidence(created.task_id)
      trace.value = await api.getTrace(created.task_id)
      phase.value = 'completed'
    } catch (error) {
      errorMessage.value = safeErrorMessage(error)
      phase.value = 'failed'
    }
  }

  function returnToEditing(): void {
    phase.value = 'editing'
    errorMessage.value = null
    optimization.value = null
    optimizing.value = false
    optimizationErrorMessage.value = null
    optimizationRequestedFields.value = []
    optimizationRequestGeneration += 1
  }

  async function requestOptimization(taskId: string, fields: WritableCopyField[]): Promise<void> {
    if (optimizing.value || !isActiveOptimizationRequest(taskId, fields)) {
      return
    }

    const requestGeneration = ++optimizationRequestGeneration
    const requestFields = [...fields]
    optimizing.value = true
    optimization.value = null
    optimizationErrorMessage.value = null
    optimizationRequestedFields.value = requestFields

    try {
      const result = await api.requestOptimization(taskId, requestFields)
      if (isCurrentOptimizationRequest(requestGeneration, taskId)) {
        if (isOptimizationResponseForRequest(result, taskId, requestFields)) {
          optimization.value = result
        } else {
          optimizationRequestedFields.value = []
          optimizationErrorMessage.value = '服务返回结果异常，请稍后重试。'
        }
      }
    } catch (error) {
      if (isCurrentOptimizationRequest(requestGeneration, taskId)) {
        optimizationErrorMessage.value = safeOptimizationErrorMessage(error)
      }
    } finally {
      if (isCurrentOptimizationRequest(requestGeneration, taskId)) {
        optimizing.value = false
      }
    }
  }

  function isActiveOptimizationRequest(taskId: string, fields: WritableCopyField[]): boolean {
    if (
      phase.value !== 'completed' ||
      task.value?.task_id !== taskId ||
      report.value?.task_id !== taskId ||
      fields.length === 0 ||
      new Set(fields).size !== fields.length
    ) {
      return false
    }

    const availableFields = new Set(
      report.value.issues
        .map((issue) => issue.field)
        .filter(isWritableCopyField),
    )
    return fields.every((field) => availableFields.has(field))
  }

  function isCurrentOptimizationRequest(requestGeneration: number, taskId: string): boolean {
    return (
      requestGeneration === optimizationRequestGeneration &&
      task.value?.task_id === taskId &&
      report.value?.task_id === taskId
    )
  }

  function isOptimizationResponseForRequest(
    result: OptimizationResult,
    taskId: string,
    requestFields: WritableCopyField[],
  ): boolean {
    return (
      result.source_task_id === taskId &&
      result.requested_fields.length === requestFields.length &&
      new Set(result.requested_fields).size === result.requested_fields.length &&
      result.requested_fields.every((field) => requestFields.includes(field))
    )
  }

  return {
    phase,
    submittedCopy,
    task,
    report,
    ruleEvidence,
    trace,
    errorMessage,
    optimization,
    optimizing,
    optimizationErrorMessage,
    optimizationRequestedFields,
    submit,
    requestOptimization,
    returnToEditing,
  }
})

function toFoodSubmission(form: FoodCopyForm): FoodWorkbenchSubmission {
  return {
    category: '食品',
    title: form.title,
    selling_points: form.sellingPointsText
      .split('\n')
      .map((item) => item.trim())
      .filter(Boolean),
    description: form.description,
    attributes: { ...form.attributes },
    marketing_description: form.marketing_description,
  }
}

function safeErrorMessage(error: unknown): string {
  if (error instanceof ApiClientError) {
    return error.message
  }
  return '质检请求失败，请稍后重试。'
}

function safeOptimizationErrorMessage(error: unknown): string {
  if (error instanceof ApiClientError) {
    return error.message
  }
  return '优化请求失败，请稍后重试。'
}

function isWritableCopyField(field: string): field is WritableCopyField {
  return (
    field === 'title' ||
    field === 'selling_points' ||
    field === 'description' ||
    field === 'marketing_description'
  )
}
