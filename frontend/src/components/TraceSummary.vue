<script setup lang="ts">
import { computed } from 'vue'

import type { SafeTraceResponse } from '../contracts/inspection'

const props = defineProps<{
  trace: SafeTraceResponse
  degradationFlags: string[]
}>()

const totalLatencyMs = computed(() =>
  props.trace.events.reduce((total, event) => total + event.latency_ms, 0),
)
const hasFailureOrDegradation = computed(
  () =>
    props.degradationFlags.length > 0 || props.trace.events.some((event) => event.status === 'failed'),
)
const summaryStatus = computed(() =>
  hasFailureOrDegradation.value ? '含失败或降级' : '全部成功',
)

function formatLatency(latencyMs: number): string {
  return latencyMs >= 1000 ? `${(latencyMs / 1000).toFixed(1)} 秒` : `${latencyMs} 毫秒`
}
</script>

<template>
  <details class="trace-summary" data-testid="trace-summary">
    <summary>
      <span class="trace-summary-title">执行与安全 Trace</span>
      <span class="trace-summary-meta">
        {{ trace.events.length }} 个步骤 · {{ formatLatency(totalLatencyMs) }} · {{ summaryStatus }}
      </span>
    </summary>
    <ol class="trace-event-list">
      <li v-for="(event, index) in trace.events" :key="`${event.step_name}-${index}`">
        <div>
          <strong>{{ event.step_name }}</strong>
          <span>{{ event.tool_or_skill_name }} · {{ event.decision }}</span>
        </div>
        <small>
          {{ event.status }} · {{ formatLatency(event.latency_ms) }}
          <template v-if="event.rule_ids.length"> · {{ event.rule_ids.join(', ') }}</template>
        </small>
      </li>
    </ol>
  </details>
</template>
