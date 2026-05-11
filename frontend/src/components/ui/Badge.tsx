import { type HTMLAttributes, type ReactNode } from 'react'
import { cx } from './utils'

type BadgeTone = 'neutral' | 'accent' | 'success' | 'warning' | 'error' | 'info'

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone
  leadingIcon?: ReactNode
}

const toneClasses: Record<BadgeTone, string> = {
  neutral: 'border-border bg-surface-overlay text-text-secondary',
  accent: 'border-accent/20 bg-accent-subtle text-accent',
  success: 'border-success/20 bg-success-subtle text-success',
  warning: 'border-warning/25 bg-warning-subtle text-warning',
  error: 'border-error/20 bg-error-subtle text-error',
  info: 'border-info/20 bg-info-subtle text-info',
}

export function Badge({
  children,
  className,
  tone = 'neutral',
  leadingIcon,
  ...props
}: BadgeProps) {
  return (
    <span
      className={cx(
        'inline-flex min-h-6 items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium',
        toneClasses[tone],
        className
      )}
      {...props}
    >
      {leadingIcon}
      {children}
    </span>
  )
}
