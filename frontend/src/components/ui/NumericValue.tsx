import { type HTMLAttributes } from 'react'
import { cx } from './utils'

export interface NumericValueProps extends HTMLAttributes<HTMLSpanElement> {}

export function NumericValue({ className, ...props }: NumericValueProps) {
  return (
    <span
      className={cx('font-mono tabular-nums tracking-normal', className)}
      {...props}
    />
  )
}
