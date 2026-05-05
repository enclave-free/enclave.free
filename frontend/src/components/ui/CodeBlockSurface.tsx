import { type HTMLAttributes, type ReactNode } from 'react'
import { cx } from './utils'

export interface CodeBlockSurfaceProps extends HTMLAttributes<HTMLDivElement> {
  label?: ReactNode
  actions?: ReactNode
}

export function CodeBlockSurface({
  children,
  className,
  label,
  actions,
  role,
  'aria-label': ariaLabel,
  ...props
}: CodeBlockSurfaceProps) {
  const labelledRegionName = typeof label === 'string' ? label : undefined

  return (
    <div
      role={role ?? (labelledRegionName ? 'region' : undefined)}
      aria-label={ariaLabel ?? labelledRegionName}
      className={cx(
        'overflow-hidden rounded-lg border border-border bg-surface text-sm shadow-sm',
        className
      )}
      {...props}
    >
      {(label || actions) && (
        <div className="flex min-h-10 items-center justify-between gap-3 border-b border-border bg-surface-raised px-3 py-2">
          {label && (
            <div className="font-mono text-xs font-medium text-text-secondary">
              {label}
            </div>
          )}
          {actions && <div className="flex items-center gap-1">{actions}</div>}
        </div>
      )}
      <div className="overflow-x-auto p-3 font-mono text-xs leading-5 text-text">
        {children}
      </div>
    </div>
  )
}
