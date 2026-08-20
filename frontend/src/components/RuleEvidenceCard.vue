<script setup lang="ts">
import type { RuleEvidence } from '../contracts/inspection'

defineProps<{ rule: RuleEvidence }>()
</script>

<template>
  <article class="rule-evidence-card" data-testid="rule-evidence">
    <p class="rule-id">{{ rule.rule_id }} · v{{ rule.version }}</p>
    <p>{{ rule.rule_text }}</p>
    <p class="rule-hint">建议：{{ rule.rewrite_hint }}</p>
  </article>
</template>
