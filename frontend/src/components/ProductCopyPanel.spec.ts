import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ProductCopyPanel from './ProductCopyPanel.vue'
import type { FoodCopyForm } from '../stores/workbench'

const form: FoodCopyForm = {
  title: '',
  sellingPointsText: '',
  description: '',
  attributes: {
    ingredients: '',
    shelf_life: '',
    storage_method: '',
    origin: '',
  },
  marketing_description: '',
}

describe('ProductCopyPanel', () => {
  it('emits edited product copy without submitting it automatically', async () => {
    const wrapper = mount(ProductCopyPanel, { props: { modelValue: form } })

    await wrapper.get('[name="title"]').setValue('茉莉花茶袋泡茶 30g')

    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([
      expect.objectContaining({ title: '茉莉花茶袋泡茶 30g' }),
    ])
    expect(wrapper.emitted('submit')).toBeUndefined()
  })
})
