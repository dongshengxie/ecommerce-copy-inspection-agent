<script setup lang="ts">
import { computed, ref } from 'vue'

import type { InspectionReport, WritableCopyField } from '../contracts/inspection'
import { useWorkbenchStore } from '../stores/workbench'

const props = defineProps<{
  taskId: string
  report: InspectionReport
}>()

const workbench = useWorkbenchStore()
const selectedFields = ref<WritableCopyField[]>([])

const fieldLabels: Record<WritableCopyField, string> = {
  title: '商品标题',
  selling_points: '商品卖点',
  description: '商品详情',
  marketing_description: '营销描述',
}

const availableFields = computed(() => {
  const fields = new Set(
    props.report.issues
      .map((issue) => issue.field)
      .filter(isWritableCopyField),
  )

  return (Object.keys(fieldLabels) as WritableCopyField[]).filter((field) => fields.has(field))
})

const canRequest = computed(() => selectedFields.value.length > 0 && !workbench.optimizing)
const visibleOptimizedFields = computed(() => {
  const result = workbench.optimization
  if (result?.status !== 'success') {
    return []
  }

  return Object.entries(result.optimized_fields).filter(
    ([field]) =>
      isWritableCopyField(field) && workbench.optimizationRequestedFields.includes(field),
  ) as [WritableCopyField, string | string[]][]
})

function toggleField(field: WritableCopyField, checked: boolean): void {
  selectedFields.value = checked
    ? [...new Set([...selectedFields.value, field])]
    : selectedFields.value.filter((item) => item !== field)
}

async function requestOptimization(): Promise<void> {
  await workbench.requestOptimization(props.taskId, selectedFields.value)
}

function optimizedText(value: string | string[]): string {
  return Array.isArray(value) ? value.join('\n') : value
}

function isWritableCopyField(field: string): field is WritableCopyField {
  return field in fieldLabels
}
</script>

<template>
  <section class="optimization-panel" aria-label="文案优化">
    <div class="optimization-heading">
      <div>
        <h3>请求优化</h3>
        <p>选择需要修改的字段后生成建议；优化不会自动执行。</p>
      </div>
    </div>

    <div v-if="availableFields.length" class="optimization-fields">
      <label v-for="field in availableFields" :key="field" class="optimization-field">
        <input
          :data-testid="`optimize-${field}`"
          type="checkbox"
          :checked="selectedFields.includes(field)"
          :disabled="workbench.optimizing"
          @change="toggleField(field, ($event.target as HTMLInputElement).checked)"
        />
        {{ fieldLabels[field] }}
      </label>
    </div>
    <p v-else class="optimization-empty">当前问题没有可优化的文案字段。</p>

    <button
      class="optimization-action"
      data-testid="request-optimization"
      type="button"
      :disabled="!canRequest"
      @click="requestOptimization"
    >
      {{ workbench.optimizing ? '正在请求优化…' : '生成优化建议' }}
    </button>

    <p v-if="workbench.optimizationErrorMessage" class="optimization-error" role="alert">
      {{ workbench.optimizationErrorMessage }}
    </p>

    <section
      v-if="workbench.optimization"
      class="optimization-result"
      data-testid="optimization-status"
      :data-status="workbench.optimization.status"
    >
      <strong v-if="workbench.optimization.status === 'success'">优化后验证通过</strong>
      <strong v-else-if="workbench.optimization.status === 'verification_failed'">
        优化后验证未通过，建议人工复核
      </strong>
      <strong v-else>优化未完成，请稍后重试或人工处理</strong>

      <dl v-if="visibleOptimizedFields.length" class="optimized-copy-list">
        <template v-for="[field, value] in visibleOptimizedFields" :key="field">
          <dt>{{ fieldLabels[field] }}</dt>
          <dd>{{ optimizedText(value) }}</dd>
        </template>
      </dl>
    </section>
  </section>
</template>
