<script setup lang="ts">
import { computed } from 'vue'

export interface EvidenceMatch {
  evidence: string
  issueNumber: number
}

interface TextSegment {
  text: string
  issueNumbers?: number[]
}

const props = withDefaults(
  defineProps<{
    text: string
    evidence?: string
    issueNumber?: number
    matches?: EvidenceMatch[]
  }>(),
  { evidence: '', issueNumber: undefined, matches: () => [] },
)

const segments = computed<TextSegment[]>(() => {
  const matches = normalizedMatches()
  if (!props.text || matches.length === 0) {
    return [{ text: props.text || '—' }]
  }

  const result: TextSegment[] = []
  const markedIssueNumbers = new Set<number>()
  let cursor = 0

  while (cursor < props.text.length) {
    const candidate = findNextMatch(props.text, cursor, matches)
    if (candidate === undefined) {
      result.push({ text: props.text.slice(cursor) })
      break
    }
    if (candidate.index > cursor) {
      result.push({ text: props.text.slice(cursor, candidate.index) })
    }
    const relatedMatches = matches.filter(
      (match) =>
        match.evidence === candidate.match.evidence &&
        props.text.indexOf(match.evidence, cursor) === candidate.index,
    )
    const issueNumbers = [...new Set(relatedMatches.map((match) => match.issueNumber))]
    result.push({
      text: candidate.match.evidence,
      issueNumbers: issueNumbers.filter((issueNumber) => !markedIssueNumbers.has(issueNumber)),
    })
    issueNumbers.forEach((issueNumber) => markedIssueNumbers.add(issueNumber))
    cursor = candidate.index + candidate.match.evidence.length
  }

  return result
})

function normalizedMatches(): EvidenceMatch[] {
  const input = props.matches.length > 0 ? props.matches : [{ evidence: props.evidence, issueNumber: props.issueNumber }]
  return input.filter(
    (match): match is EvidenceMatch =>
      typeof match.issueNumber === 'number' && match.issueNumber > 0 && match.evidence.length > 0,
  )
}

function findNextMatch(
  text: string,
  cursor: number,
  matches: EvidenceMatch[],
): { index: number; match: EvidenceMatch } | undefined {
  const candidates = matches
    .map((match) => ({ index: text.indexOf(match.evidence, cursor), match }))
    .filter((candidate) => candidate.index >= 0)
    .sort((left, right) => left.index - right.index || right.match.evidence.length - left.match.evidence.length)
  return candidates[0]
}
</script>

<template>
  <span class="evidence-text">
    <template v-for="(segment, index) in segments" :key="`${segment.text}-${index}`">
      <mark v-if="segment.issueNumbers !== undefined" data-testid="evidence-highlight" class="evidence-highlight">
        {{ segment.text }}
        <sup
          v-for="issueNumber in segment.issueNumbers"
          :key="issueNumber"
          data-testid="issue-marker"
          class="issue-marker"
        >
          {{ issueNumber }}
        </sup>
      </mark>
      <template v-else>{{ segment.text }}</template>
    </template>
  </span>
</template>
