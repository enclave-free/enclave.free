import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { cx } from './Button'

type IconButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
type IconButtonSize = 'sm' | 'md' | 'lg'

export interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'aria-label'> {
  label: string
  pressed?: boolean
  variant?: IconButtonVariant
  size?: IconButtonSize
}

const variantClasses: Record<IconButtonVariant, string> = {
  primary: 'btn-primary',
  secondary: 'btn-secondary',
  ghost: 'btn-ghost',
  danger: 'btn-danger',
}

const sizeClasses: Record<IconButtonSize, string> = {
  sm: 'h-10 w-10 p-2',
  md: 'h-10 w-10 p-2',
  lg: 'h-11 w-11 p-2.5',
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  {
    children,
    className,
    label,
    pressed,
    type = 'button',
    variant = 'ghost',
    size = 'md',
    ...props
  },
  ref
) {
  return (
    <button
      ref={ref}
      type={type}
      aria-label={label}
      aria-pressed={pressed}
      title={props.title ?? label}
      className={cx(
        'btn inline-flex shrink-0 items-center justify-center focus-ring',
        variantClasses[variant],
        sizeClasses[size],
        pressed !== undefined && 'data-[pressed=true]:bg-surface-overlay data-[pressed=true]:text-text',
        className
      )}
      data-pressed={pressed}
      {...props}
    >
      {children}
    </button>
  )
})
