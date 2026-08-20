<script setup lang="ts">
import { computed, ref } from 'vue'

import AppSidebar from '../components/AppSidebar.vue'
import FoodAttributesPanel from '../components/FoodAttributesPanel.vue'
import InspectionRunState from '../components/InspectionRunState.vue'
import ProductCopyPanel from '../components/ProductCopyPanel.vue'
import WorkflowProgress from '../components/WorkflowProgress.vue'
import { createEmptyFoodCopyForm, useWorkbenchStore, type FoodCopyForm } from '../stores/workbench'

const workbench = useWorkbenchStore()
const form = ref<FoodCopyForm>(createEmptyFoodCopyForm())
const semanticEnabled = ref(false)
const activeTab = ref<'copy' | 'attributes'>('copy')

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

function updateCopy(value: FoodCopyForm): void {
  form.value = value
}

function updateAttributes(value: FoodCopyForm['attributes']): void {
  form.value = { ...form.value, attributes: value }
}

async function submit(): Promise<void> {
  await workbench.submit(form.value, semanticEnabled.value)
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
          <form @submit.prevent="submit">
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
          <h2>问题与证据</h2>
          <p class="panel-eyebrow">质检结果</p>
          <InspectionRunState
            class="run-state"
            :phase="workbench.phase"
            :error-message="workbench.errorMessage"
          />
          <div v-if="workbench.phase === 'editing'" class="state-placeholder">
            <strong>等待文案提交</strong>
            <p>提交食品文案后，这里将显示来自质检报告的风险问题与证据定位。</p>
          </div>
          <div v-else-if="workbench.phase === 'completed'" class="state-placeholder">
            <strong>质检报告已获取</strong>
            <p>问题筛选、数字证据定位与任务级复核结论将在下一步呈现。</p>
          </div>
        </article>

        <article class="workbench-panel panel-detail" data-testid="detail-panel">
          <h2>问题详情与优化</h2>
          <p class="panel-eyebrow">规则依据 · 显式操作</p>
          <div class="state-placeholder">
            <strong v-if="workbench.phase === 'completed'">请选择一个问题</strong>
            <strong v-else>等待质检结果</strong>
            <p>
              这里仅展示后端返回的规则依据和用户明确请求的优化结果，不自动生成或采纳修改。
            </p>
          </div>
        </article>
      </section>
    </main>
  </div>
</template>
