/**
 * useValidation.spec.js — 表单验证测试套件
 * 
 * 测试范围:
 * - 验证规则 (required, pattern, min, max, custom)
 * - 错误消息显示
 * - 验证时机 (blur, input, submit)
 * - 表单整体验证状态
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useValidation, createValidators, validateForm } from '../../src/composables/useValidation.js'

describe('useValidation', () => {
  describe('Validation Rules', () => {
    let validators

    beforeEach(() => {
      validators = createValidators()
    })

    // ============================================
    // 必填验证
    // ============================================
    describe('required', () => {
      it('should fail for empty string', () => {
        const result = validators.required('')
        expect(result.valid).toBe(false)
        expect(result.message).toBeTruthy()
      })

      it('should fail for null/undefined', () => {
        expect(validators.required(null).valid).toBe(false)
        expect(validators.required(undefined).valid).toBe(false)
      })

      it('should fail for whitespace-only string', () => {
        expect(validators.required('   ').valid).toBe(false)
      })

      it('should pass for non-empty string', () => {
        expect(validators.required('test').valid).toBe(true)
      })

      it('should pass for number 0', () => {
        expect(validators.required(0).valid).toBe(true)
      })

      it('should pass for empty array if not strict', () => {
        expect(validators.required([], { strict: false }).valid).toBe(true)
      })

      it('should fail for empty array if strict', () => {
        expect(validators.required([], { strict: true }).valid).toBe(false)
      })

      it('should use custom message', () => {
        const result = validators.required('', { message: '请填写此字段' })
        expect(result.message).toBe('请填写此字段')
      })
    })

    // ============================================
    // 模式验证
    // ============================================
    describe('pattern', () => {
      it('should validate regex pattern', () => {
        const result = validators.pattern('abc123', /^[a-z]+$/)
        expect(result.valid).toBe(false)
      })

      it('should pass for matching pattern', () => {
        const result = validators.pattern('abc', /^[a-z]+$/)
        expect(result.valid).toBe(true)
      })

      it('should pass for empty value (use required for empty check)', () => {
        const result = validators.pattern('', /^[a-z]+$/)
        expect(result.valid).toBe(true)
      })

      it('should validate stock symbol pattern', () => {
        const stockPattern = /^(sh|sz)[0-9]{6}$/
        expect(validators.pattern('sh600519', stockPattern).valid).toBe(true)
        expect(validators.pattern('sz000001', stockPattern).valid).toBe(true)
        expect(validators.pattern('600519', stockPattern).valid).toBe(false)
        expect(validators.pattern('sh60051', stockPattern).valid).toBe(false)
      })

      it('should use custom message', () => {
        const result = validators.pattern('INVALID', /^[a-z]+$/, { message: '格式错误' })
        expect(result.message).toBe('格式错误')
      })
    })

    // ============================================
    // 最小值验证
    // ============================================
    describe('min', () => {
      it('should fail for value below minimum', () => {
        expect(validators.min(5, 10).valid).toBe(false)
      })

      it('should pass for value at minimum', () => {
        expect(validators.min(10, 10).valid).toBe(true)
      })

      it('should pass for value above minimum', () => {
        expect(validators.min(15, 10).valid).toBe(true)
      })

      it('should validate string length', () => {
        expect(validators.min('ab', 3).valid).toBe(false)
        expect(validators.min('abc', 3).valid).toBe(true)
      })

      it('should pass for empty value (use required for empty check)', () => {
        expect(validators.min('', 3).valid).toBe(true)
      })

      it('should use custom message', () => {
        const result = validators.min(5, 10, { message: '最小值为10' })
        expect(result.message).toBe('最小值为10')
      })
    })

    // ============================================
    // 最大值验证
    // ============================================
    describe('max', () => {
      it('should fail for value above maximum', () => {
        expect(validators.max(15, 10).valid).toBe(false)
      })

      it('should pass for value at maximum', () => {
        expect(validators.max(10, 10).valid).toBe(true)
      })

      it('should pass for value below maximum', () => {
        expect(validators.max(5, 10).valid).toBe(true)
      })

      it('should validate string length', () => {
        expect(validators.max('abcd', 3).valid).toBe(false)
        expect(validators.max('abc', 3).valid).toBe(true)
      })

      it('should pass for empty value', () => {
        expect(validators.max('', 3).valid).toBe(true)
      })
    })

    // ============================================
    // 范围验证
    // ============================================
    describe('range', () => {
      it('should fail for value outside range', () => {
        expect(validators.range(5, [10, 20]).valid).toBe(false)
        expect(validators.range(25, [10, 20]).valid).toBe(false)
      })

      it('should pass for value in range', () => {
        expect(validators.range(15, [10, 20]).valid).toBe(true)
      })

      it('should pass for value at boundaries', () => {
        expect(validators.range(10, [10, 20]).valid).toBe(true)
        expect(validators.range(20, [10, 20]).valid).toBe(true)
      })

      it('should pass for empty value', () => {
        expect(validators.range('', [10, 20]).valid).toBe(true)
      })
    })

    // ============================================
    // 邮箱验证
    // ============================================
    describe('email', () => {
      it('should validate email format', () => {
        expect(validators.email('test@example.com').valid).toBe(true)
        expect(validators.email('user.name@domain.co.uk').valid).toBe(true)
      })

      it('should fail for invalid email', () => {
        expect(validators.email('invalid').valid).toBe(false)
        expect(validators.email('test@').valid).toBe(false)
        expect(validators.email('@domain.com').valid).toBe(false)
      })

      it('should pass for empty value', () => {
        expect(validators.email('').valid).toBe(true)
      })
    })

    // ============================================
    // 自定义验证
    // ============================================
    describe('custom', () => {
      it('should use custom validator function', () => {
        const customValidator = (value) => ({
          valid: value === 'secret',
          message: '值不正确'
        })
        
        expect(validators.custom('secret', customValidator).valid).toBe(true)
        expect(validators.custom('wrong', customValidator).valid).toBe(false)
      })

      it('should support async validator', async () => {
        const asyncValidator = async (value) => {
          await new Promise(r => setTimeout(r, 10))
          return { valid: value === 'valid', message: '异步验证失败' }
        }
        
        const result1 = await validators.custom('valid', asyncValidator)
        expect(result1.valid).toBe(true)
        
        const result2 = await validators.custom('invalid', asyncValidator)
        expect(result2.valid).toBe(false)
      })
    })
  })

  // ============================================
  // useValidation Composable Tests
  // ============================================
  describe('useValidation Composable', () => {
    it('should create field with initial state', () => {
      const { field } = useValidation({
        symbol: { value: '', rules: ['required'] }
      })

      expect(field('symbol').value).toBe('')
      expect(field('symbol').error).toBe('')
      expect(field('symbol').touched).toBe(false)
      expect(field('symbol').dirty).toBe(false)
    })

    it('should validate on blur by default', async () => {
      const { field, validateField } = useValidation({
        symbol: { value: '', rules: ['required'] }
      })

      expect(field('symbol').value).toBe('')
      expect(field('symbol').error).toBe('')
      expect(field('symbol').touched).toBe(false)
      expect(field('symbol').dirty).toBe(false)

      await validateField('symbol')
      expect(field('symbol').error).toBeTruthy()
      expect(field('symbol').touched).toBe(true)
    })

    it('should validate on input when configured', async () => {
      const { field, handleInput } = useValidation({
        symbol: { value: '', rules: ['required'], validateOnInput: true }
      })

      await handleInput('symbol', '')
      expect(field('symbol').error).toBeTruthy()
      expect(field('symbol').touched).toBe(true)
    })

    it('should clear error on valid input', async () => {
      const { field, validateField, handleInput } = useValidation({
        symbol: { value: '', rules: ['required'] }
      })

      await validateField('symbol')
      expect(field('symbol').error).toBeTruthy()

      await handleInput('symbol', 'valid value')
      expect(field('symbol').error).toBe('')
    })

    it('should track dirty state', () => {
      const { field, handleInput } = useValidation({
        symbol: { value: '' }
      })

      expect(field('symbol').dirty).toBe(false)
      
      handleInput('symbol', 'changed')
      expect(field('symbol').dirty).toBe(true)
    })

    it('should validate all fields on submit', async () => {
      const { validateAll, isValid, field } = useValidation({
        name: { value: '', rules: ['required'] },
        email: { value: '', rules: ['required', 'email'] }
      })

      const result = await validateAll()
      
      expect(result).toBe(false)
      expect(isValid.value).toBe(false)
      expect(field('name').error).toBeTruthy()
      expect(field('email').error).toBeTruthy()
    })

    it('should return true when all fields valid', async () => {
      const { validateAll, isValid } = useValidation({
        name: { value: 'John', rules: ['required'] },
        email: { value: 'john@example.com', rules: ['required', 'email'] }
      })

      const result = await validateAll()
      
      expect(result).toBe(true)
      expect(isValid.value).toBe(true)
    })

    it('should reset field state', () => {
      const { field, validateField, resetField } = useValidation({
        symbol: { value: 'test', rules: ['required'] }
      })

      validateField('symbol')
      expect(field('symbol').touched).toBe(true)

      resetField('symbol')
      expect(field('symbol').value).toBe('')
      expect(field('symbol').error).toBe('')
      expect(field('symbol').touched).toBe(false)
      expect(field('symbol').dirty).toBe(false)
    })

    it('should reset all fields', () => {
      const { field, validateAll, resetAll } = useValidation({
        name: { value: 'test', rules: ['required'] },
        email: { value: 'test@example.com', rules: ['email'] }
      })

      validateAll()
      
      resetAll()
      
      expect(field('name').value).toBe('')
      expect(field('name').error).toBe('')
      expect(field('email').value).toBe('')
      expect(field('email').error).toBe('')
    })

    it('should support custom validation rules', async () => {
      const { field, validateField } = useValidation({
        symbol: {
          value: 'invalid',
          rules: [{
            name: 'stockSymbol',
            validate: (v) => /^(sh|sz)[0-9]{6}$/.test(v),
            message: '股票代码格式错误，应为 sh/sz + 6位数字'
          }]
        }
      })

      await validateField('symbol')
      expect(field('symbol').error).toBe('股票代码格式错误，应为 sh/sz + 6位数字')

      field('symbol').value = 'sh600519'
      await validateField('symbol')
      expect(field('symbol').error).toBe('')
    })

    it('should support multiple validation rules', async () => {
      const { field, validateField, handleInput } = useValidation({
        price: {
          value: '',
          rules: ['required', { name: 'min', params: 0 }, { name: 'max', params: 1000 }]
        }
      })

      await validateField('price')
      expect(field('price').error).toBeTruthy()

      await handleInput('price', '-5')
      await validateField('price')
      expect(field('price').error).toContain('最小')

      await handleInput('price', '1500')
      await validateField('price')
      expect(field('price').error).toContain('最大')

      await handleInput('price', '500')
      await validateField('price')
      expect(field('price').error).toBe('')
    })
  })

  // ============================================
  // validateForm Helper Tests
  // ============================================
  describe('validateForm Helper', () => {
    it('should validate form data against schema', async () => {
      const schema = {
        name: ['required'],
        email: ['required', 'email'],
        age: [{ name: 'min', params: 18 }]
      }

      const data = {
        name: '',
        email: 'invalid-email',
        age: 15
      }

      const result = await validateForm(data, schema)
      
      expect(result.valid).toBe(false)
      expect(result.errors.name).toBeTruthy()
      expect(result.errors.email).toBeTruthy()
      expect(result.errors.age).toBeTruthy()
    })

    it('should return valid for correct data', async () => {
      const schema = {
        name: ['required'],
        email: ['required', 'email'],
        age: [{ name: 'min', params: 18 }]
      }

      const data = {
        name: 'John',
        email: 'john@example.com',
        age: 25
      }

      const result = await validateForm(data, schema)
      
      expect(result.valid).toBe(true)
      expect(result.errors).toEqual({})
    })

    it('should ignore fields not in schema', async () => {
      const schema = {
        name: ['required']
      }

      const data = {
        name: 'John',
        extraField: 'ignored'
      }

      const result = await validateForm(data, schema)
      
      expect(result.valid).toBe(true)
    })
  })

  // ============================================
  // Timing Tests
  // ============================================
  describe('Validation Timing', () => {
    it('should validate on blur by default', async () => {
      const { field, handleBlur } = useValidation({
        symbol: { value: '', rules: ['required'] }
      })

      expect(field('symbol').error).toBe('')
      expect(field('symbol').touched).toBe(false)

      await handleBlur('symbol')
      
      expect(field('symbol').error).toBeTruthy()
      expect(field('symbol').touched).toBe(true)
    })

    it('should not validate on input by default', () => {
      const { field, handleInput } = useValidation({
        symbol: { value: '', rules: ['required'] }
      })

      handleInput('symbol', '')
      
      expect(field('symbol').error).toBe('')
      expect(field('symbol').touched).toBe(false)
    })

    it('should validate on input when validateOnInput is true', async () => {
      const { field, handleInput } = useValidation({
        symbol: { value: '', rules: ['required'], validateOnInput: true }
      })

      await handleInput('symbol', '')
      
      expect(field('symbol').error).toBeTruthy()
    })

    it('should debounce validation on input', async () => {
      const { field, handleInput } = useValidation({
        symbol: { value: '', rules: ['required'], validateOnInput: true, debounce: 50 }
      })

      handleInput('symbol', '')
      handleInput('symbol', 'a')
      handleInput('symbol', '')
      
      // Immediately after - debounce should delay validation
      expect(field('symbol').error).toBe('')
      
      // Wait for debounce
      await new Promise(r => setTimeout(r, 100))
      
      expect(field('symbol').error).toBeTruthy()
    })

    it('should validate all fields on submit regardless of touched state', async () => {
      const { validateAll, field } = useValidation({
        name: { value: '', rules: ['required'] },
        email: { value: '', rules: ['required'] }
      })

      // Fields not touched yet
      expect(field('name').touched).toBe(false)
      expect(field('email').touched).toBe(false)

      await validateAll()
      
      // After submit, all fields should be touched and validated
      expect(field('name').touched).toBe(true)
      expect(field('email').touched).toBe(true)
      expect(field('name').error).toBeTruthy()
      expect(field('email').error).toBeTruthy()
    })
  })

  // ============================================
  // Error Message Display Tests
  // ============================================
  describe('Error Message Display', () => {
    it('should show error only when touched', async () => {
      const { field, handleBlur } = useValidation({
        symbol: { value: '', rules: ['required'] }
      })

      expect(field('symbol').showError).toBe(false)
      
      await handleBlur('symbol')
      
      expect(field('symbol').showError).toBe(true)
    })

    it('should hide error when field becomes valid', async () => {
      const { field, handleBlur, handleInput } = useValidation({
        symbol: { value: '', rules: ['required'] }
      })

      await handleBlur('symbol')
      expect(field('symbol').showError).toBe(true)

      await handleInput('symbol', 'valid')
      expect(field('symbol').showError).toBe(false)
    })

    it('should provide accessible error attributes', async () => {
      const { field, handleBlur, getAriaAttributes } = useValidation({
        symbol: { value: '', rules: ['required'] }
      })

      await handleBlur('symbol')
      
      const aria = getAriaAttributes('symbol')
      
      expect(aria['aria-invalid']).toBe('true')
      expect(aria['aria-describedby']).toBeTruthy()
    })

    it('should mark field as valid when no error', () => {
      const { field, handleInput, getAriaAttributes } = useValidation({
        symbol: { value: 'valid', rules: ['required'] }
      })

      handleInput('symbol', 'valid')
      
      const aria = getAriaAttributes('symbol')
      
      expect(aria['aria-invalid']).toBe('false')
    })
  })
})
