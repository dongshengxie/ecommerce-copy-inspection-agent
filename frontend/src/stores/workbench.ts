import { ref } from 'vue'
import { defineStore } from 'pinia'

import { api } from '../api/inspections'
import { ApiClientError } from '../api/client'
import type {
  FoodAttributes,
  FoodWorkbenchSubmission,
  InspectionReport,
  InspectionTask,
  RuleEvidenceResponse,
  SafeTraceResponse,
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
  }

  return {
    phase,
    submittedCopy,
    task,
    report,
    ruleEvidence,
    trace,
    errorMessage,
    submit,
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
