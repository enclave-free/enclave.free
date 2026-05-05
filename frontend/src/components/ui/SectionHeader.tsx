import { type HTMLAttributes, type ReactNode } from 'react'
import { cx } from './Button'

export interface SectionHeaderProps extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
}

export function SectionHeader({
  title,
  description,
  actions,
  className,
  ...props
}: SectionHeaderProps) {
  return (
    <div className={cx('flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between', className)} {...props}>
      <div className="min-w-0 space-y-1">
        <h2 className="text-base font-semibold tracking-normal text-text">{title}</h2>
        {description && (
          <p className="max-w-2xl text-sm leading-6 text-text-secondary">{description}</p>
        )}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  )
}
