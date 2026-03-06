import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';
import { SecretValueText } from '../SecretValueEditor';

interface SecretValueRevealCellProps {
  value: string | null;
  revealed: boolean;
  tone?: 'default' | 'inherited';
  maskedContent?: ReactNode;
  missingContent?: ReactNode;
  maskedClassName?: string;
  valueClassName?: string;
  revealContainerClassName?: string;
}

export function SecretValueRevealCell({
  value,
  revealed,
  tone = 'default',
  maskedContent = '••••••••••••',
  missingContent,
  maskedClassName,
  valueClassName,
  revealContainerClassName
}: SecretValueRevealCellProps) {
  if (value === null) {
    return missingContent ?? <span className="text-sm text-muted-foreground">Missing</span>;
  }

  if (!revealed) {
    return (
      <span className={cn('font-mono text-sm text-muted-foreground', maskedClassName)}>
        {maskedContent}
      </span>
    );
  }

  return (
    <div
      className={cn(
        'w-full max-w-full rounded-md border border-border px-2 py-1',
        tone === 'inherited' ? 'bg-muted/10' : 'bg-muted/20',
        revealContainerClassName
      )}
    >
      <SecretValueText value={value} className={cn('max-h-40 overflow-x-hidden overflow-y-auto', valueClassName)} />
    </div>
  );
}
