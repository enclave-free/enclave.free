import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'
import { Check, ChevronDown, FileText } from 'lucide-react'
import { Badge, Button } from '../ui'

export interface DocumentSource {
  id: string
  name: string
  description: string
  tags: string[]
}

interface DocumentScopeProps {
  selectedDocuments: string[]
  onToggle: (docId: string) => void
  documents: DocumentSource[]
  compact?: boolean
}

export function DocumentScope({
  selectedDocuments,
  onToggle,
  documents,
  compact = false,
}: DocumentScopeProps) {
  const { t } = useTranslation()
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const [dropdownPosition, setDropdownPosition] = useState({ top: 0, left: 0, openUpward: false })

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  useEffect(() => {
    if (isOpen && buttonRef.current) {
      const updatePosition = () => {
        if (buttonRef.current) {
          const rect = buttonRef.current.getBoundingClientRect()
          const dropdownHeight = 280 // estimated max height
          const spaceBelow = window.innerHeight - rect.bottom
          const spaceAbove = rect.top
          const openUpward = spaceBelow < dropdownHeight && spaceAbove > spaceBelow

          setDropdownPosition({
            top: openUpward ? rect.top - 6 : rect.bottom + 6,
            left: rect.left,
            openUpward,
          })
        }
      }

      updatePosition()
      window.addEventListener('scroll', updatePosition, true)
      window.addEventListener('resize', updatePosition)

      return () => {
        window.removeEventListener('scroll', updatePosition, true)
        window.removeEventListener('resize', updatePosition)
      }
    }
  }, [isOpen])

  const selectedCount = selectedDocuments.length
  const triggerLabel = selectedCount > 0
    ? t('chat.documentScope.docsLabelWithCount', { count: selectedCount })
    : t('chat.documentScope.docsLabel')

  const dropdownContent = isOpen ? (
    <div
      ref={dropdownRef}
      className="fixed w-64 bg-surface-raised border border-border rounded-xl shadow-xl z-[9999] flex flex-col animate-fade-in-scale backdrop-blur-dropdown"
      style={{
        top: dropdownPosition.openUpward ? 'auto' : `${dropdownPosition.top}px`,
        bottom: dropdownPosition.openUpward ? `${window.innerHeight - dropdownPosition.top}px` : 'auto',
        left: `${dropdownPosition.left}px`,
        maxHeight: `${dropdownPosition.openUpward ? dropdownPosition.top - 16 : window.innerHeight - dropdownPosition.top - 16}px`,
      }}
    >
      <div className="px-3 py-3 border-b border-border shrink-0">
        <h4 className="heading-sm">{t('chat.documentScope.title')}</h4>
        <p className="text-[10px] text-text-muted mt-1">
          {t('chat.documentScope.description')}
        </p>
      </div>

      <div className="overflow-y-auto flex-1 min-h-0">
        {documents.length === 0 ? (
          <div className="p-4 text-center text-text-muted text-xs">{t('chat.documentScope.noSources')}</div>
        ) : (
          <div className="p-1.5">
            {documents.map((source) => {
              const isSelected = selectedDocuments.includes(source.id)
              return (
                <button
                  key={source.id}
                  onClick={() => onToggle(source.id)}
                  aria-pressed={isSelected}
                  className={`w-full text-left p-2.5 rounded-lg mb-1 last:mb-0 transition-all ${
                    isSelected
                      ? 'bg-accent/10 border border-accent/30'
                      : 'hover:bg-surface-overlay border border-transparent'
                  }`}
                >
                  <div className="flex items-start gap-2.5">
                    <div
                      className={`mt-0.5 w-4 h-4 rounded border-2 flex items-center justify-center shrink-0 transition-colors ${
                        isSelected ? 'bg-accent border-accent' : 'border-border'
                      }`}
                    >
                      {isSelected && (
                        <Check className="h-2.5 w-2.5 text-accent-text" aria-hidden="true" strokeWidth={3} />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-text">{source.name}</p>
                      <p className="text-[10px] text-text-muted mt-0.5 line-clamp-1">
                        {source.description}
                      </p>
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {source.tags.slice(0, 2).map((tag) => (
                          <span
                            key={tag}
                            className="text-[9px] bg-surface-overlay text-text-muted px-1.5 py-0.5 rounded"
                          >
                            {tag}
                          </span>
                        ))}
                        {source.tags.length > 2 && (
                          <span className="text-[9px] text-text-muted">
                            +{source.tags.length - 2}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </button>
              )
            })}
          </div>
        )}
      </div>

      {selectedCount > 0 && (
        <div className="px-3 py-2 border-t border-border shrink-0">
          <button
            onClick={() => selectedDocuments.forEach((id) => onToggle(id))}
            aria-label={t('chat.documentScope.clearAllSelectedAria', 'Clear all selected documents')}
            className="text-[10px] text-text-muted hover:text-text transition-colors"
          >
            {t('chat.documentScope.clearAll')}
          </button>
        </div>
      )}
    </div>
  ) : null

  return (
    <div className="relative">
      <Button
        ref={buttonRef}
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        aria-haspopup="dialog"
        aria-label={triggerLabel}
        variant={selectedCount > 0 ? 'primary' : 'ghost'}
        size="sm"
        leadingIcon={<FileText className="h-3.5 w-3.5" aria-hidden="true" />}
        trailingIcon={
          <ChevronDown
            className={`h-3 w-3 transition-transform ${isOpen ? 'rotate-180' : ''}`}
            aria-hidden="true"
          />
        }
        className={selectedCount > 0 ? 'text-xs shadow-md glow-accent' : 'text-xs'}
      >
        {compact ? null : t('chat.documentScope.docsLabel')}
        {selectedCount > 0 && (
          <Badge tone="neutral" className="min-h-5 border-accent-text/20 bg-accent-text/20 px-1 text-[10px] text-accent-text">
            {selectedCount}
          </Badge>
        )}
      </Button>

      {typeof document !== 'undefined' && createPortal(dropdownContent, document.body)}
    </div>
  )
}
