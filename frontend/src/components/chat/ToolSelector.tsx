import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Database, Search } from 'lucide-react';
import { Button } from '../ui';
import { cx } from '../ui/utils';

export interface Tool {
  id: string;
  name: string;
  icon: React.ReactNode;
  description: string;
}

interface ToolSelectorProps {
  tools?: Tool[];
  selectedTools: string[];
  onToggle: (toolId: string) => void;
  compact?: boolean;
  disabledToolIds?: readonly string[];
}

export function ToolSelector({
  tools,
  selectedTools,
  onToggle,
  compact = false,
  disabledToolIds = [],
}: ToolSelectorProps) {
  const { t } = useTranslation();

  const defaultTools: Tool[] = useMemo(
    () => [
      {
        id: 'web-search',
        name: t('chat.tools.webSearchName'),
        description: t('chat.tools.webSearch'),
        icon: <Search className="h-3.5 w-3.5" aria-hidden="true" />,
      },
      {
        id: 'db-query',
        name: t('chat.tools.databaseName'),
        description: t('chat.tools.database'),
        icon: <Database className="h-3.5 w-3.5" aria-hidden="true" />,
      },
    ],
    [t]
  );

  const activeTools = tools ?? defaultTools;

  return (
    <div
      className={cx(
        'flex items-center gap-1.5',
        compact && 'min-w-0 max-w-full flex-1 flex-wrap'
      )}
    >
      {!compact && <span className="label mr-1">{t('chat.tools.label')}</span>}
      {activeTools.map((tool) => {
        const isSelected = selectedTools.includes(tool.id);
        const isDisabled = disabledToolIds.includes(tool.id);
        return (
          <Button
            key={tool.id}
            onClick={() => onToggle(tool.id)}
            disabled={isDisabled}
            aria-pressed={isSelected}
            variant={isSelected ? 'primary' : 'ghost'}
            size="sm"
            leadingIcon={tool.icon}
            className={cx('text-xs', compact && 'min-w-0 shrink-0 px-2.5')}
            title={tool.description}
          >
            {tool.name}
          </Button>
        );
      })}
    </div>
  );
}
