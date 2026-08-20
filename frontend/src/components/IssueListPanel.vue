<script setup lang="ts">
import { computed, ref } from 'vue'

import type { Issue } from '../contracts/inspection'

const props = defineProps<{
  issues: Issue[]
  selectedIndex: number | null
}>()

const emit = defineEmits<{ select: [index: number] }>()

const filter = ref<'all' | 'high'>('all')
const visibleIssues = computed(() =>
  props.issues
    .map((issue, index) => ({ issue, index }))
    .filter(({ issue }) => filter.value === 'all' || issue.risk_level === 'high'),
)

function riskLabel(level: Issue['risk_level']): string {
  return { pass: '通过', low: '低风险', medium: '中风险', high: '高风险' }[level]
}
</script>

<template>
  <div class="issue-list-panel">
    <div class="issue-panel-heading">
      <div>
        <h2>发现 {{ issues.length }} 个问题</h2>
        <p class="panel-eyebrow">质检结果</p>
      </div>
      <div class="issue-filters" aria-label="问题筛选">
        <button
          type="button"
          data-testid="filter-all"
          :data-active="filter === 'all'"
          @click="filter = 'all'"
        >
          全部 {{ issues.length }}
        </button>
        <button
          type="button"
          data-testid="filter-high"
          :data-active="filter === 'high'"
          @click="filter = 'high'"
        >
          高风险 {{ issues.filter((issue) => issue.risk_level === 'high').length }}
        </button>
      </div>
    </div>

    <div v-if="visibleIssues.length" class="issue-card-list">
      <button
        v-for="({ issue, index }) in visibleIssues"
        :key="`${issue.field}-${index}`"
        type="button"
        class="issue-card"
        :class="`risk-${issue.risk_level}`"
        :data-testid="`issue-card-${index + 1}`"
        :data-selected="selectedIndex === index"
        @click="emit('select', index)"
      >
        <span class="issue-number">{{ index + 1 }}</span>
        <span class="issue-card-copy">
          <strong>{{ issue.issue_type }}</strong>
          <span>“{{ issue.evidence_span }}”</span>
          <small>
            <span class="risk-badge" :class="`risk-${issue.risk_level}`">{{ riskLabel(issue.risk_level) }}</span>
            {{ issue.rule_ids.join(' · ') || '未关联规则 ID' }}
          </small>
        </span>
        <span class="issue-chevron" aria-hidden="true">›</span>
      </button>
    </div>
    <div v-else class="state-placeholder compact-placeholder">
      <strong>未发现可展示的问题</strong>
      <p>当前筛选条件下没有匹配的风险项。</p>
    </div>
  </div>
</template>
