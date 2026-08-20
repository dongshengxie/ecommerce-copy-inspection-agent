<script setup lang="ts">
import type { WorkbenchPhase } from '../stores/workbench'

defineProps<{
  phase: WorkbenchPhase
  errorMessage: string | null
}>()
</script>

<template>
  <p v-if="phase === 'submitting' || phase === 'loading_result'" role="status">
    正在质检，语义质检可能需要较长时间。
  </p>
  <p v-else-if="phase === 'failed' && errorMessage" role="alert">{{ errorMessage }}</p>
  <p v-else-if="phase === 'completed'" role="status">质检完成。</p>
</template>
