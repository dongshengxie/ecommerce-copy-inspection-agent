<script setup lang="ts">
import { computed } from 'vue'

import type { Issue, RuleEvidence } from '../contracts/inspection'
import RuleEvidenceCard from './RuleEvidenceCard.vue'

const props = defineProps<{
  issue: Issue | null
  issueNumber: number | null
  rules: RuleEvidence[]
}>()

const relatedRules = computed(() => {
  if (props.issue === null) return []
  return props.rules.filter((rule) => props.issue?.rule_ids.includes(rule.rule_id))
})

const riskLabel = computed(() => {
  if (props.issue === null) return ''
  return { pass: '通过', low: '低风险', medium: '中风险', high: '高风险' }[props.issue.risk_level]
})

const fieldLabel = computed(() => {
  if (props.issue === null) return ''
  const labels: Record<string, string> = {
    title: '商品标题',
    selling_points: '商品卖点',
    description: '商品详情',
    marketing_description: '营销描述',
    'attributes.ingredients': '配料',
    'attributes.shelf_life': '保质期',
    'attributes.storage_method': '贮存方式',
    'attributes.origin': '产地',
    'attributes.applicable_people': '适用人群',
    'attributes.net_content': '净含量',
    'attributes.brand': '品牌',
  }
  return labels[props.issue.field] ?? props.issue.field
})
</script>

<template>
  <div v-if="issue" class="issue-detail-panel">
    <div class="detail-heading">
      <span class="risk-badge" :class="`risk-${issue.risk_level}`">{{ riskLabel }}</span>
      <span class="detail-number">问题 {{ issueNumber }}</span>
    </div>
    <h2>{{ issue.issue_type }}</h2>
    <section class="detail-section">
      <h3>证据定位</h3>
      <p><strong>{{ fieldLabel }}</strong> · “{{ issue.evidence_span }}”</p>
    </section>
    <section class="detail-section">
      <h3>修改建议</h3>
      <p>{{ issue.suggestion }}</p>
    </section>
    <section class="detail-section">
      <h3>规则依据</h3>
      <div v-if="relatedRules.length" class="rule-evidence-list">
        <RuleEvidenceCard v-for="rule in relatedRules" :key="`${rule.rule_id}-${rule.version}`" :rule="rule" />
      </div>
      <p v-else class="rule-fallback">关联 Rule ID：{{ issue.rule_ids.join(' · ') || '暂无' }}</p>
    </section>
  </div>
  <div v-else class="state-placeholder">
    <strong>请选择一个问题</strong>
    <p>选择问题后查看其证据定位、项目方提供的规则依据和修改建议。</p>
  </div>
</template>
