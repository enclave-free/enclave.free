import { type HTMLAttributes, type ReactNode } from 'react'
import { NumericValue } from './NumericValue'
import { cx } from './utils'

type MetricTone = 'accent' | 'success' | 'warning' | 'error' | 'neutral'

export interface MetricCardProps extends HTMLAttributes<HTMLDivElement> {
  label: ReactNode
  value: ReactNode
  description?: ReactNode
  tone?: MetricTone
}

const toneClasses: Record<MetricTone, string> = {
  accent: 'text-accent',
  success: 'text-success',
  warning: 'text-warning',
  error: 'text-error',
  neutral: 'text-text',
}

export function MetricCard({
  className,
  children,
  description,
  label,
  tone = 'accent',
  value,
  'aria-label': ariaLabel,
  ...props
}: MetricCardProps) {
  const accessibleName = typeof label === 'string' ? label : undefined

  return (
    <div
      role="group"
      aria-label={ariaLabel ?? accessibleName}
      className={cx('rounded-lg bg-surface-overlay p-4', className)}
      {...props}
    >
      <p className="text-sm font-medium text-text">{label}</p>
      <NumericValue className={cx('block text-2xl font-bold', toneClasses[tone])}>
        {value}
      </NumericValue>
      {description && (
        <p className="text-xs text-text-secondary">
          {description}
        </p>
      )}
      {children}
    </div>
  )
}
