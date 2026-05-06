import { useTranslation } from 'react-i18next'
import { CustomField } from '../../types/onboarding'
import { SelectField, Textarea, TextField } from '../ui'

interface DynamicFieldProps {
  field: CustomField
  value: string | boolean
  onChange: (value: string | boolean) => void
  error?: string
}

export function DynamicField({ field, value, onChange, error }: DynamicFieldProps) {
  const { t } = useTranslation()
  const placeholder = field.placeholder || t('onboarding.profile.enterField', { field: field.name.toLowerCase() })

  const renderInput = () => {
    switch (field.type) {
      case 'text':
      case 'email':
      case 'url':
        return (
          <TextField
            label={field.name}
            type={field.type}
            value={value as string}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            required={field.required}
            error={error}
          />
        )

      case 'number':
        return (
          <TextField
            label={field.name}
            type="number"
            value={value as string}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            required={field.required}
            error={error}
          />
        )

      case 'date':
        return (
          <TextField
            label={field.name}
            type="date"
            value={value as string}
            onChange={(e) => onChange(e.target.value)}
            required={field.required}
            error={error}
          />
        )

      case 'textarea':
        return (
          <Textarea
            label={field.name}
            value={value as string}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            rows={3}
            required={field.required}
            error={error}
          />
        )

      case 'select':
        return (
          <SelectField
            label={field.name}
            value={value as string}
            onChange={(e) => onChange(e.target.value)}
            required={field.required}
            error={error}
          >
            <option value="">{t('onboarding.profile.selectOption')}</option>
            {field.options?.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </SelectField>
        )

      case 'checkbox':
        return (
          <label className="flex items-center gap-3 cursor-pointer py-2">
            <div
              className={`w-5 h-5 rounded-md border-2 flex items-center justify-center transition-colors ${
                value
                  ? 'bg-accent border-accent'
                  : 'border-border hover:border-accent/50'
              }`}
              onClick={() => onChange(!value)}
            >
              {value && (
                <svg
                  className="w-3 h-3 text-accent-text"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={3}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              )}
            </div>
            <span className="text-sm text-text">{field.placeholder || field.name}</span>
          </label>
        )

      default:
        return null
    }
  }

  return (
    <div>
      {renderInput()}
    </div>
  )
}
