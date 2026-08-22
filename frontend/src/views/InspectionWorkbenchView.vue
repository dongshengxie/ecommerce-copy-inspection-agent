<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import AppSidebar from '../components/AppSidebar.vue'
import FoodAttributesPanel from '../components/FoodAttributesPanel.vue'
import EvidenceMarkedText, { type EvidenceMatch } from '../components/EvidenceMarkedText.vue'
import InspectionRunState from '../components/InspectionRunState.vue'
import InspectionSummary from '../components/InspectionSummary.vue'
import IssueDetailPanel from '../components/IssueDetailPanel.vue'
import IssueListPanel from '../components/IssueListPanel.vue'
import OptimizationPanel from '../components/OptimizationPanel.vue'
import ProductCopyPanel from '../components/ProductCopyPanel.vue'
import TraceSummary from '../components/TraceSummary.vue'
import WorkflowProgress from '../components/WorkflowProgress.vue'
import { createEmptyFoodCopyForm, useWorkbenchStore, type FoodCopyForm } from '../stores/workbench'

const workbench = useWorkbenchStore()
const form = ref<FoodCopyForm>(createEmptyFoodCopyForm())
const semanticEnabled = ref(false)
const activeTab = ref<'copy' | 'attributes'>('copy')
const selectedIssueIndex = ref<number | null>(null)

const canSubmit = computed(() => {
  const attributes = form.value.attributes
  return Boolean(
    form.value.title.trim() &&
      form.value.sellingPointsText.trim() &&
      form.value.description.trim() &&
      form.value.marketing_description.trim() &&
      attributes.ingredients.trim() &&
      attributes.shelf_life.trim() &&
      attributes.storage_method.trim() &&
      attributes.origin.trim(),
  )
})

const taskLabel = computed(() => workbench.submittedCopy?.title || '新建食品质检任务')
const statusLabel = computed(() => {
  if (workbench.phase === 'completed') return '质检完成'
  if (workbench.phase === 'submitting' || workbench.phase === 'loading_result') return '质检中'
  if (workbench.phase === 'failed') return '质检未完成'
  return '待提交'
})
const statusState = computed(() => {
  if (workbench.phase === 'completed') return 'completed'
  if (workbench.phase === 'submitting' || workbench.phase === 'loading_result') return 'running'
  return 'editing'
})
const selectedIssue = computed(() => {
  if (selectedIssueIndex.value === null) return null
  return workbench.report?.issues[selectedIssueIndex.value] ?? null
})

watch(
  () => workbench.report?.task_id,
  () => {
    selectedIssueIndex.value = workbench.report?.issues.length ? 0 : null
  },
)

function updateCopy(value: FoodCopyForm): void {
  form.value = value
}

function updateAttributes(value: FoodCopyForm['attributes']): void {
  form.value = { ...form.value, attributes: value }
}

async function submit(): Promise<void> {
  await workbench.submit(form.value, semanticEnabled.value)
}

function evidenceMatches(field: string): EvidenceMatch[] {
  return (workbench.report?.issues ?? [])
    .map((issue, index) => ({ issue, index }))
    .filter(({ issue }) => issue.field === field)
    .map(({ issue, index }) => ({
      evidence: issue.evidence_span,
      issueNumber: index + 1,
      riskLevel: issue.risk_level,
    }))
}

function attributeText(value: unknown): string {
  return value === null || value === undefined || value === '' ? '—' : String(value)
}
</script>

<template>
  <div class="workbench-page">
    <AppSidebar />
    <main class="workbench-main" aria-label="食品文案质检工作台">
      <header class="task-header">
        <div>
          <h1 class="app-title">电商文案质检 Agent</h1>
          <div class="task-caption">
            <h2 class="task-title">
              <span class="task-title-prefix">质检任务 / </span>{{ taskLabel }}
            </h2>
            <span class="task-status" :data-state="statusState">
              <span aria-hidden="true">●</span>{{ statusLabel }}
            </span>
          </div>
        </div>
      </header>

      <WorkflowProgress :phase="workbench.phase" />

      <section class="workbench-grid" aria-label="质检工作区">
        <article class="workbench-panel panel-copy" data-testid="copy-panel">
          <h2>原始商品文案</h2>
          <p class="panel-eyebrow">食品 · 当前会话内保存</p>
          <div class="panel-tabs" role="tablist" aria-label="商品输入内容">
            <button
              type="button"
              role="tab"
              :aria-selected="activeTab === 'copy'"
              :data-active="activeTab === 'copy'"
              @click="activeTab = 'copy'"
            >
              基础文案
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="activeTab === 'attributes'"
              :data-active="activeTab === 'attributes'"
              @click="activeTab = 'attributes'"
            >
              食品属性
            </button>
          </div>
          <template v-if="workbench.phase === 'completed' && workbench.submittedCopy">
            <section v-if="activeTab === 'copy'" class="copy-document" aria-label="已提交基础文案">
              <div>
                <h3>商品标题</h3>
                <EvidenceMarkedText
                  :text="workbench.submittedCopy.title"
                  :matches="evidenceMatches('title')"
                />
              </div>
              <div>
                <h3>商品卖点</h3>
                <p v-for="point in workbench.submittedCopy.selling_points" :key="point">
                  <EvidenceMarkedText :text="point" :matches="evidenceMatches('selling_points')" />
                </p>
              </div>
              <div>
                <h3>商品详情</h3>
                <p>
                  <EvidenceMarkedText
                    :text="workbench.submittedCopy.description"
                    :matches="evidenceMatches('description')"
                  />
                </p>
              </div>
              <div>
                <h3>营销描述</h3>
                <p>
                  <EvidenceMarkedText
                    :text="workbench.submittedCopy.marketing_description"
                    :matches="evidenceMatches('marketing_description')"
                  />
                </p>
              </div>
            </section>
            <dl v-else class="attributes-document" aria-label="已提交食品属性">
              <template v-for="(value, key) in workbench.submittedCopy.attributes" :key="key">
                <dt>{{ key }}</dt>
                <dd>
                  <EvidenceMarkedText
                    :text="attributeText(value)"
                    :matches="evidenceMatches(`attributes.${String(key)}`)"
                  />
                </dd>
              </template>
            </dl>
          </template>
          <form v-else @submit.prevent="submit">
            <ProductCopyPanel
              v-if="activeTab === 'copy'"
              :model-value="form"
              @update:model-value="updateCopy"
            />
            <FoodAttributesPanel
              v-else
              :model-value="form.attributes"
              @update:model-value="updateAttributes"
            />
            <label class="semantic-option">
              <input v-model="semanticEnabled" type="checkbox" />
              启用语义质检（可能增加时间与模型费用）
            </label>
            <button
              class="form-action"
              data-testid="submit-inspection"
              :disabled="
                !canSubmit || workbench.phase === 'submitting' || workbench.phase === 'loading_result'
              "
            >
              开始质检
            </button>
          </form>
        </article>

        <article class="workbench-panel panel-issues" data-testid="issue-panel">
          <InspectionRunState
            v-if="workbench.phase !== 'editing' && workbench.phase !== 'completed'"
            class="run-state"
            :phase="workbench.phase"
            :error-message="workbench.errorMessage"
          />
          <div v-if="workbench.phase === 'editing'" class="state-placeholder">
            <strong>等待文案提交</strong>
            <p>提交食品文案后，这里将显示来自质检报告的风险问题与证据定位。</p>
          </div>
          <IssueListPanel
            v-else-if="workbench.report"
            :issues="workbench.report.issues"
            :selected-index="selectedIssueIndex"
            @select="selectedIssueIndex = $event"
          />
        </article>

        <article class="workbench-panel panel-detail" data-testid="detail-panel">
          <IssueDetailPanel
            v-if="workbench.report"
            :issue="selectedIssue"
            :issue-number="selectedIssueIndex === null ? null : selectedIssueIndex + 1"
            :rules="workbench.ruleEvidence?.rules ?? []"
          />
          <OptimizationPanel
            v-if="workbench.report && workbench.task"
            :task-id="workbench.task.task_id"
            :report="workbench.report"
          />
          <div v-else class="state-placeholder">
            <strong>等待质检结果</strong>
            <p>这里仅展示后端返回的规则依据和用户明确请求的优化结果，不自动生成或采纳修改。</p>
          </div>
        </article>
      </section>
      <InspectionSummary v-if="workbench.report" :report="workbench.report" />
      <TraceSummary
        v-if="workbench.trace && workbench.report"
        :trace="workbench.trace"
        :degradation-flags="workbench.report.degradation_flags"
      />
    </main>
  </div>
</template>
