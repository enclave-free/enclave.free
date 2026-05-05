import { useId, useState, type ReactNode } from 'react'
import { ChevronDown } from 'lucide-react'
import { Badge } from './Badge'
import { Card } from './Card'
import { cx } from './utils'

export interface DisclosureCardProps {
  title: ReactNode
  children: ReactNode
  badge?: ReactNode
  className?: string
  defaultOpen?: boolean
  eyebrow?: ReactNode
  icon?: ReactNode
}

export function DisclosureCard({
  title,
  children,
  badge,
  className,
  defaultOpen = false,
  eyebrow,
  icon,
}: DisclosureCardProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen)
  const contentId = useId()

  return (
    <Card className={className} padding="lg">
      <button
        type="button"
        aria-expanded={isOpen}
        aria-controls={contentId}
        onClick={() => setIsOpen((current) => !current)}
        className="focus-ring flex min-h-10 w-full items-center justify-between gap-4 rounded-lg text-left"
      >
        <span className="flex min-w-0 items-center gap-2">
          {icon}
          {eyebrow && (
            <span className="font-mono text-sm font-semibold text-text-muted tabular-nums">
              {eyebrow}
            </span>
          )}
          <span className="truncate text-lg font-semibold text-text">{title}</span>
          {badge && <Badge tone="accent">{badge}</Badge>}
        </span>
        <ChevronDown
          className={cx(
            'h-5 w-5 shrink-0 text-text-muted transition-transform',
            isOpen && 'rotate-180'
          )}
          aria-hidden="true"
        />
      </button>
      {isOpen && (
        <div id={contentId} className="mt-4 border-t border-border pt-4">
          {children}
        </div>
      )}
    </Card>
  )
}
