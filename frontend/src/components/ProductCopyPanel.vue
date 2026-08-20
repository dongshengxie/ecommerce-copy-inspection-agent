<script setup lang="ts">
import type { FoodCopyForm } from '../stores/workbench'

const props = defineProps<{ modelValue: FoodCopyForm }>()

const emit = defineEmits<{ 'update:modelValue': [value: FoodCopyForm] }>()

type CopyField = 'title' | 'sellingPointsText' | 'description' | 'marketing_description'

function updateField(field: CopyField, event: Event): void {
  const value = (event.target as HTMLInputElement | HTMLTextAreaElement).value
  emit('update:modelValue', { ...props.modelValue, [field]: value })
}
</script>

<template>
  <section aria-label="基础文案">
    <h2>基础文案</h2>
    <label>
      商品标题
      <input
        name="title"
        :value="modelValue.title"
        required
        @input="updateField('title', $event)"
      />
    </label>
    <label>
      商品卖点
      <textarea
        name="selling-points"
        :value="modelValue.sellingPointsText"
        required
        placeholder="每行一个卖点"
        @input="updateField('sellingPointsText', $event)"
      />
    </label>
    <label>
      商品详情
      <textarea
        name="description"
        :value="modelValue.description"
        required
        @input="updateField('description', $event)"
      />
    </label>
    <label>
      营销描述
      <textarea
        name="marketing-description"
        :value="modelValue.marketing_description"
        required
        @input="updateField('marketing_description', $event)"
      />
    </label>
  </section>
</template>
