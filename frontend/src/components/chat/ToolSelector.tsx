import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Database, Search } from 'lucide-react';
import { Button } from '../ui';

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
}

export function ToolSelector({
  tools,
  selectedTools,
  onToggle,
  compact = false,
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
    <div className="flex items-center gap-1.5">
      {!compact && <span className="label mr-1">{t('chat.tools.label')}</span>}
      {activeTools.map((tool) => {
        const isSelected = selectedTools.includes(tool.id);
        return (
          <Button
            key={tool.id}
            onClick={() => onToggle(tool.id)}
            aria-pressed={isSelected}
            variant={isSelected ? 'primary' : 'ghost'}
            size="sm"
            leadingIcon={tool.icon}
            className="text-xs"
            title={tool.description}
          >
            {tool.name}
          </Button>
        );
      })}
    </div>
  );
}
