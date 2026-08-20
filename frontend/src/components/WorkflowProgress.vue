<script setup lang="ts">
import { computed } from 'vue'

import type { WorkbenchPhase } from '../stores/workbench'

const props = defineProps<{ phase: WorkbenchPhase }>()

const activeStep = computed(() => {
  if (props.phase === 'editing' || props.phase === 'failed') {
    return 1
  }
  return 2
})

const completedStep = computed(() => (props.phase === 'completed' ? 2 : activeStep.value - 1))

const steps = ['文案录入', '智能质检', '优化确认', '二次校验']
</script>

<template>
  <ol class="workflow-progress" aria-label="质检流程">
    <li
      v-for="(label, index) in steps"
      :key="label"
      class="workflow-step"
      :data-testid="`workflow-step-${index === 0 ? 'entry' : index + 1}`"
      :data-active="activeStep === index + 1"
      :data-complete="completedStep >= index + 1"
    >
      <span class="workflow-number">{{ index + 1 }}</span>
      <span class="workflow-label">{{ label }}</span>
    </li>
  </ol>
</template>
