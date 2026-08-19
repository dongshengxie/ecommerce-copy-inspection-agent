export type RiskLevel = 'pass' | 'low' | 'medium' | 'high'

export type TaskStatus = 'running' | 'success' | 'failed'

export type WritableCopyField =
  | 'title'
  | 'selling_points'
  | 'description'
  | 'marketing_description'

export interface FoodAttributes {
  ingredients: string
  shelf_life: string
  storage_method: string
  origin: string
  applicable_people?: string | null
  net_content?: string | null
  brand?: string | null
  [key: string]: unknown
}

export interface FoodWorkbenchSubmission {
  category: '食品'
  title: string
  selling_points: string[]
  description: string
  attributes: FoodAttributes
  marketing_description: string
}

export interface CreatedInspection {
  task_id: string
  status: string
  result_url: string
}

export interface InspectionTask {
  task_id: string
  status: string
  trigger_source: string
  rule_version: string
}

export interface Issue {
  field: string
  issue_type: string
  risk_level: RiskLevel
  evidence_span: string
  evidence: string
  rule_ids: string[]
  source: string[]
  confidence: number
  suggestion: string
}

export interface InspectionReport {
  task_id: string
  status: TaskStatus
  automated_risk_level: RiskLevel
  review_required: boolean
  review_reasons: string[]
  issues: Issue[]
  degradation_flags: string[]
  trace_id: string
}

export interface RuleEvidence {
  rule_id: string
  version: string
  field_scope: string[]
  risk_level: RiskLevel
  rule_text: string
  rewrite_hint: string
}

export interface RuleEvidenceResponse {
  task_id: string
  rules: RuleEvidence[]
}

export interface SafeTraceEvent {
  step_name: string
  tool_or_skill_name: string
  rule_ids: string[]
  decision: string
  status: 'success' | 'failed'
  latency_ms: number
  metadata: Record<string, unknown>
}

export interface SafeTraceResponse {
  task_id: string
  events: SafeTraceEvent[]
}

export interface OptimizationIssueReference {
  field: string
  evidence_span: string
  rule_ids: string[]
}

export interface OptimizationResult {
  optimization_id: string
  source_task_id: string
  status: 'success' | 'verification_failed' | 'failed'
  requested_fields: WritableCopyField[]
  optimized_fields: Partial<Record<WritableCopyField, string | string[]>>
  referenced_issues: OptimizationIssueReference[]
  referenced_rule_ids: string[]
  verification_report: InspectionReport | null
  failure_reason: string | null
}
