<script setup lang="ts">
import { computed, ref } from 'vue'

import FoodAttributesPanel from '../components/FoodAttributesPanel.vue'
import InspectionRunState from '../components/InspectionRunState.vue'
import ProductCopyPanel from '../components/ProductCopyPanel.vue'
import { createEmptyFoodCopyForm, useWorkbenchStore, type FoodCopyForm } from '../stores/workbench'

const workbench = useWorkbenchStore()
const form = ref<FoodCopyForm>(createEmptyFoodCopyForm())
const semanticEnabled = ref(false)

const canSubmit = computed(() => {
  const attributes = form.value.attributes
  return Boolean(
    form.value.title.trim() &&
      form.value.sellingPointsText.trim() &&
      form.value.description.trim() &&
      form.value.marketing_description.trim() &&
      attributes.ingredients.trim() &&
      attributes.shelf_life.trim() &&
      attributes.storage_method.trim() &&
      attributes.origin.trim(),
  )
})

function updateCopy(value: FoodCopyForm): void {
  form.value = value
}

function updateAttributes(value: FoodCopyForm['attributes']): void {
  form.value = { ...form.value, attributes: value }
}

async function submit(): Promise<void> {
  await workbench.submit(form.value, semanticEnabled.value)
}
</script>

<template>
  <main aria-label="文案质检工作台">
    <h1>电商文案质检 Agent</h1>
    <p>当前支持食品类目质检。</p>
    <form @submit.prevent="submit">
      <ProductCopyPanel :model-value="form" @update:model-value="updateCopy" />
      <FoodAttributesPanel :model-value="form.attributes" @update:model-value="updateAttributes" />
      <label>
        <input v-model="semanticEnabled" type="checkbox" />
        启用语义质检（可能需要更长时间）
      </label>
      <button :disabled="!canSubmit || workbench.phase === 'submitting' || workbench.phase === 'loading_result'">
        开始质检
      </button>
    </form>
    <InspectionRunState :phase="workbench.phase" :error-message="workbench.errorMessage" />
  </main>
</template>
