import type {
  CreatedInspection,
  FoodWorkbenchSubmission,
  InspectionReport,
  InspectionTask,
  OptimizationResult,
  RuleEvidenceResponse,
  SafeTraceResponse,
  WritableCopyField,
} from '../contracts/inspection'

import { HttpClient } from './client'

class InspectionApi {
  constructor(private readonly client: HttpClient) {}

  submitWorkbenchInspection(
    input: FoodWorkbenchSubmission,
    semanticEnabled: boolean,
  ): Promise<CreatedInspection> {
    return this.client.requestJson('/api/v2/workbench/inspections', {
      method: 'POST',
      body: input,
      headers: {
        'X-Semantic-Inspection': semanticEnabled ? 'enabled' : 'disabled',
      },
      validate: isCreatedInspection,
    })
  }

  getInspection(taskId: string): Promise<InspectionTask> {
    return this.client.requestJson(`/api/v2/inspections/${encodeURIComponent(taskId)}`, {
      method: 'GET',
      validate: isInspectionTask,
    })
  }

  getResult(taskId: string): Promise<InspectionReport> {
    return this.client.requestJson(`/api/v2/inspections/${encodeURIComponent(taskId)}/result`, {
      method: 'GET',
      validate: isInspectionReport,
    })
  }

  getRuleEvidence(taskId: string): Promise<RuleEvidenceResponse> {
    return this.client.requestJson(
      `/api/v2/inspections/${encodeURIComponent(taskId)}/rule-evidence`,
      { method: 'GET', validate: isRuleEvidenceResponse },
    )
  }

  getTrace(taskId: string): Promise<SafeTraceResponse> {
    return this.client.requestJson(`/api/v2/inspections/${encodeURIComponent(taskId)}/trace`, {
      method: 'GET',
      validate: isSafeTraceResponse,
    })
  }

  requestOptimization(
    taskId: string,
    fields: WritableCopyField[],
  ): Promise<OptimizationResult> {
    return this.client.requestJson(
      `/api/v2/inspections/${encodeURIComponent(taskId)}/optimization`,
      {
        method: 'POST',
        body: { fields },
        validate: isOptimizationResult,
      },
    )
  }
}

export const api = new InspectionApi(new HttpClient())

function isCreatedInspection(value: Record<string, unknown>): value is CreatedInspection {
  return hasString(value, 'task_id') && hasString(value, 'status') && hasString(value, 'result_url')
}

function isInspectionTask(value: Record<string, unknown>): value is InspectionTask {
  return (
    hasString(value, 'task_id') &&
    hasString(value, 'status') &&
    hasString(value, 'trigger_source') &&
    hasString(value, 'rule_version')
  )
}

function isInspectionReport(value: Record<string, unknown>): value is InspectionReport {
  return (
    hasString(value, 'task_id') &&
    isTaskStatus(value.status) &&
    isRiskLevel(value.automated_risk_level) &&
    typeof value.review_required === 'boolean' &&
    isArray(value.review_reasons) &&
    isArray(value.issues) &&
    isArray(value.degradation_flags) &&
    hasString(value, 'trace_id')
  )
}

function isRuleEvidenceResponse(value: Record<string, unknown>): value is RuleEvidenceResponse {
  return hasString(value, 'task_id') && isArray(value.rules)
}

function isSafeTraceResponse(value: Record<string, unknown>): value is SafeTraceResponse {
  return hasString(value, 'task_id') && isArray(value.events)
}

function isOptimizationResult(value: Record<string, unknown>): value is OptimizationResult {
  return (
    hasString(value, 'optimization_id') &&
    hasString(value, 'source_task_id') &&
    isOptimizationStatus(value.status) &&
    isArray(value.requested_fields) &&
    isRecord(value.optimized_fields) &&
    isArray(value.referenced_issues) &&
    isArray(value.referenced_rule_ids) &&
    (value.verification_report === null || isRecord(value.verification_report)) &&
    (value.failure_reason === null || typeof value.failure_reason === 'string')
  )
}

function hasString(value: Record<string, unknown>, key: string): boolean {
  return typeof value[key] === 'string'
}

function isArray(value: unknown): value is unknown[] {
  return Array.isArray(value)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isTaskStatus(value: unknown): boolean {
  return value === 'running' || value === 'success' || value === 'failed'
}

function isRiskLevel(value: unknown): boolean {
  return value === 'pass' || value === 'low' || value === 'medium' || value === 'high'
}

function isOptimizationStatus(value: unknown): boolean {
  return value === 'success' || value === 'verification_failed' || value === 'failed'
}
