import { type HTMLAttributes, type ReactNode } from 'react'
import { cx } from './Button'

export interface PageShellProps extends HTMLAttributes<HTMLDivElement> {
  header?: ReactNode
  footer?: ReactNode
  width?: 'md' | 'lg' | 'xl' | 'full'
}

const widthClasses = {
  md: 'max-w-3xl',
  lg: 'max-w-5xl',
  xl: 'max-w-7xl',
  full: 'max-w-none',
}

export function PageShell({
  children,
  className,
  header,
  footer,
  width = 'lg',
  ...props
}: PageShellProps) {
  return (
    <main className={cx('min-h-screen px-4 py-6 sm:px-6 lg:px-8', className)} {...props}>
      <div className={cx('mx-auto flex w-full flex-col gap-6', widthClasses[width])}>
        {header}
        {children}
        {footer}
      </div>
    </main>
  )
}
