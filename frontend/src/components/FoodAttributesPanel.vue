<script setup lang="ts">
import type { FoodAttributes } from '../contracts/inspection'

const props = defineProps<{ modelValue: FoodAttributes }>()

const emit = defineEmits<{ 'update:modelValue': [value: FoodAttributes] }>()

type AttributeField =
  | 'ingredients'
  | 'shelf_life'
  | 'storage_method'
  | 'origin'
  | 'applicable_people'
  | 'net_content'
  | 'brand'

function updateField(field: AttributeField, event: Event): void {
  const value = (event.target as HTMLInputElement).value
  emit('update:modelValue', { ...props.modelValue, [field]: value })
}
</script>

<template>
  <section aria-label="食品属性">
    <h2>食品属性</h2>
    <label>
      配料
      <input
        name="ingredients"
        :value="modelValue.ingredients"
        required
        @input="updateField('ingredients', $event)"
      />
    </label>
    <label>
      保质期
      <input
        name="shelf-life"
        :value="modelValue.shelf_life"
        required
        @input="updateField('shelf_life', $event)"
      />
    </label>
    <label>
      贮存方式
      <input
        name="storage-method"
        :value="modelValue.storage_method"
        required
        @input="updateField('storage_method', $event)"
      />
    </label>
    <label>
      产地
      <input name="origin" :value="modelValue.origin" required @input="updateField('origin', $event)" />
    </label>
    <label>
      适用人群（选填）
      <input
        name="applicable-people"
        :value="modelValue.applicable_people ?? ''"
        @input="updateField('applicable_people', $event)"
      />
    </label>
    <label>
      净含量（选填）
      <input
        name="net-content"
        :value="modelValue.net_content ?? ''"
        @input="updateField('net_content', $event)"
      />
    </label>
    <label>
      品牌（选填）
      <input name="brand" :value="modelValue.brand ?? ''" @input="updateField('brand', $event)" />
    </label>
  </section>
</template>
