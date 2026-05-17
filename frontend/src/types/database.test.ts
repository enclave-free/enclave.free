import { describe, expect, it } from 'vitest'
import { isJsonValue } from './database'

describe('Admin Database Explorer value helpers', () => {
  it('recognizes only parseable JSON strings as JSON values', () => {
    expect(isJsonValue('{"role":"admin"}')).toBe(true)
    expect(isJsonValue('  {"role":"admin"}  ')).toBe(true)
    expect(isJsonValue('[1,2,3]')).toBe(true)
    expect(isJsonValue('{role:admin}')).toBe(false)
    expect(isJsonValue('[1,2,]')).toBe(false)
  })

  it('does not mark scalar cell text as expandable JSON', () => {
    expect(isJsonValue('"active"')).toBe(false)
    expect(isJsonValue('42')).toBe(false)
    expect(isJsonValue('true')).toBe(false)
  })
})
