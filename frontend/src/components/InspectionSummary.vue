<script setup lang="ts">
import { computed } from 'vue'

import type { InspectionReport } from '../contracts/inspection'

const props = defineProps<{ report: InspectionReport }>()

const summary = computed(() =>
  props.report.review_required
    ? `质检完成 · 发现 ${props.report.issues.length} 个问题 · 需要人工复核`
    : `质检完成 · 发现 ${props.report.issues.length} 个问题`,
)
</script>

<template>
  <section class="inspection-summary" data-testid="inspection-summary">
    <span aria-hidden="true">✓</span>
    <strong>{{ summary }}</strong>
  </section>
</template>
