import { describe, expect, it } from 'vitest'

import { categoryCapabilities, getSubmissionCapability } from './categories'

describe('category capabilities', () => {
  it('only exposes food as an enabled submission category', () => {
    expect(categoryCapabilities.food.enabled).toBe(true)
    expect(getSubmissionCapability('food')).toEqual(categoryCapabilities.food)
    expect(getSubmissionCapability('beauty')).toBeUndefined()
    expect(getSubmissionCapability('homeAppliance')).toBeUndefined()
  })
})
