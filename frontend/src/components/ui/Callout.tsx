import { type HTMLAttributes, type ReactNode } from 'react'
import { cx } from './utils'

type CalloutTone = 'accent' | 'success' | 'warning' | 'error'

export interface CalloutProps extends HTMLAttributes<HTMLDivElement> {
  label: string
  tone?: CalloutTone
  children: ReactNode
}

const toneClasses: Record<CalloutTone, string> = {
  accent: 'border-accent',
  success: 'border-success',
  warning: 'border-warning',
  error: 'border-error',
}

export function Callout({
  children,
  className,
  label,
  tone = 'accent',
  ...props
}: CalloutProps) {
  return (
    <div
      role="note"
      aria-label={label}
      className={cx(
        'rounded-r-lg border-l-4 bg-surface-overlay px-4 py-3 text-sm text-text-secondary',
        toneClasses[tone],
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}
