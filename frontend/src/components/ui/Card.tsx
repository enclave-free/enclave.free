import { type HTMLAttributes } from 'react'
import { cx } from './utils'

type CardPadding = 'none' | 'sm' | 'md' | 'lg'

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  padding?: CardPadding
  interactive?: boolean
}

const paddingClasses: Record<CardPadding, string> = {
  none: '',
  sm: 'p-4',
  md: 'p-5',
  lg: 'p-6',
}

export function Card({
  children,
  className,
  padding = 'md',
  interactive = false,
  ...props
}: CardProps) {
  return (
    <div
      className={cx(
        'rounded-lg border border-border bg-surface-raised shadow-sm',
        paddingClasses[padding],
        interactive && 'card-interactive',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}
