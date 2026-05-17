import { useState, useRef, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Download, FileText } from 'lucide-react'
import { Message } from './ChatMessage'
import { downloadExport, ExportFormat } from '../../utils/exportChat'
import { useInstanceConfig } from '../../context/InstanceConfigContext'
import { IconButton } from '../ui'

interface ExportButtonProps {
  messages: Message[]
  disabled?: boolean
  iconOnly?: boolean
}

export function ExportButton({ messages, disabled, iconOnly = false }: ExportButtonProps) {
  const { t } = useTranslation()
  const { config } = useInstanceConfig()
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleExport = (format: ExportFormat) => {
    downloadExport({
      messages,
      format,
      translations: {
        defaultTitle: t('chat.export.defaultTitle'),
        roleUser: t('chat.export.roleUser'),
        roleAssistant: t('chat.export.roleAssistant'),
        footer: t('chat.export.footer'),
        exportedOn: t('chat.export.exportedOn'),
        copiedExportNotice: t(
          'chat.export.copiedExportNotice',
          'This export leaves active product storage and is outside Active Storage Lifecycle after download.'
        ),
      },
      instanceName: config.name,
    })
    setIsOpen(false)
  }

  const isDisabled = disabled || messages.length === 0
  useEffect(() => {
    if (isDisabled) setIsOpen(false)
  }, [isDisabled])

  const buttonTitle = isDisabled ? t('chat.export.disabled') : t('chat.export.title')
  const exportIcon = <Download className="h-4 w-4" aria-hidden="true" />

  return (
    <div className="relative" ref={dropdownRef}>
      {iconOnly ? (
        <IconButton
          label={buttonTitle}
          onClick={() => !isDisabled && setIsOpen(!isOpen)}
          disabled={isDisabled}
          pressed={isOpen}
          className={isDisabled ? 'text-text-muted! cursor-not-allowed' : undefined}
        >
          {exportIcon}
        </IconButton>
      ) : (
        <button
          onClick={() => !isDisabled && setIsOpen(!isOpen)}
          disabled={isDisabled}
          className={`btn-ghost inline-flex items-center justify-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-all ${
            isDisabled
              ? 'text-text-muted! cursor-not-allowed'
              : ''
          }`}
          title={buttonTitle}
        >
          {exportIcon}
          {t('chat.export.button')}
        </button>
      )}

      {isOpen && (
        <div className="absolute top-full right-0 mt-1.5 w-44 bg-surface-raised border border-border rounded-xl shadow-xl z-50 overflow-hidden animate-fade-in-scale backdrop-blur-dropdown">
          <div className="p-1.5">
            <button
              onClick={() => handleExport('md')}
              className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-text hover:bg-surface-overlay rounded-lg transition-colors text-left"
            >
              <FileText className="h-4 w-4 text-text-muted" aria-hidden="true" />
              <div>
                <p className="font-medium">{t('chat.export.markdown')}</p>
                <p className="text-[10px] text-text-muted">{t('chat.export.markdownExt')}</p>
              </div>
            </button>
            <button
              onClick={() => handleExport('txt')}
              className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-text hover:bg-surface-overlay rounded-lg transition-colors text-left"
            >
              <FileText className="h-4 w-4 text-text-muted" aria-hidden="true" />
              <div>
                <p className="font-medium">{t('chat.export.plainText')}</p>
                <p className="text-[10px] text-text-muted">{t('chat.export.plainTextExt')}</p>
              </div>
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
