<script setup lang="ts">
import { computed } from 'vue'

import type { RiskLevel } from '../contracts/inspection'

export interface EvidenceMatch {
  evidence: string
  issueNumber: number
  riskLevel?: RiskLevel
}

interface TextSegment {
  text: string
  issueMarkers?: EvidenceMatch[]
  highestRiskLevel?: RiskLevel
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
    const relatedMatches = findOverlappingMatches(props.text, cursor, candidate, matches)
    const issueMarkers = uniqueIssueMarkers(relatedMatches)
    const unmarkedIssueMarkers = issueMarkers.filter(
      (marker) => !markedIssueNumbers.has(marker.issueNumber),
    )
    const endIndex = Math.max(
      ...relatedMatches.map(
        (match) => props.text.indexOf(match.evidence, cursor) + match.evidence.length,
      ),
    )
    result.push({
      text: props.text.slice(candidate.index, endIndex),
      issueMarkers: unmarkedIssueMarkers,
      highestRiskLevel: highestRiskLevel(issueMarkers),
    })
    issueMarkers.forEach((marker) => markedIssueNumbers.add(marker.issueNumber))
    cursor = endIndex
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

function uniqueIssueMarkers(matches: EvidenceMatch[]): EvidenceMatch[] {
  return [...new Map(matches.map((match) => [match.issueNumber, match])).values()].sort(
    (left, right) => left.issueNumber - right.issueNumber,
  )
}

function highestRiskLevel(matches: EvidenceMatch[]): RiskLevel {
  const riskOrder: Record<RiskLevel, number> = { pass: 0, low: 1, medium: 2, high: 3 }
  return matches.reduce<RiskLevel>(
    (highest, match) => (riskOrder[match.riskLevel ?? 'medium'] > riskOrder[highest] ? match.riskLevel ?? 'medium' : highest),
    'pass',
  )
}

function findOverlappingMatches(
  text: string,
  cursor: number,
  candidate: { index: number; match: EvidenceMatch },
  matches: EvidenceMatch[],
): EvidenceMatch[] {
  const relatedMatches = [candidate.match]
  let endIndex = candidate.index + candidate.match.evidence.length
  let expanded = true

  while (expanded) {
    expanded = false
    for (const match of matches) {
      const startIndex = text.indexOf(match.evidence, cursor)
      const matchEndIndex = startIndex + match.evidence.length
      if (
        startIndex >= candidate.index &&
        startIndex < endIndex &&
        !relatedMatches.includes(match)
      ) {
        relatedMatches.push(match)
        if (matchEndIndex > endIndex) {
          endIndex = matchEndIndex
          expanded = true
        }
      }
    }
  }

  return relatedMatches
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
      <mark
        v-if="segment.issueMarkers !== undefined"
        data-testid="evidence-highlight"
        class="evidence-highlight"
        :class="`risk-${segment.highestRiskLevel ?? 'medium'}`"
      >
        {{ segment.text }}
        <sup
          v-for="marker in segment.issueMarkers"
          :key="marker.issueNumber"
          data-testid="issue-marker"
          class="issue-marker"
          :class="`risk-${marker.riskLevel ?? 'medium'}`"
        >
          {{ marker.issueNumber }}
        </sup>
      </mark>
      <template v-else>{{ segment.text }}</template>
    </template>
  </span>
</template>
