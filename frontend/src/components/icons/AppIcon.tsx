import { lazy, Suspense } from 'react';
import { KeyRoundIcon } from 'lucide-react';
import { cn } from '../../lib/utils';

const IconifyIcon = lazy(async () => {
  const module = await import('@iconify/react');
  return { default: module.Icon };
});

const ICON_SLUG_PATTERN = /^[a-z0-9-]+:[a-z0-9][a-z0-9-]*$/;
const DEFAULT_ICON = 'lucide:key-round';

interface AppIconProps {
  icon?: string | null;
  className?: string;
  title?: string;
}

function sanitizeIconSlug(value?: string | null): string {
  const normalized = value?.trim().toLowerCase() ?? '';
  if (!ICON_SLUG_PATTERN.test(normalized)) {
    return DEFAULT_ICON;
  }
  return normalized;
}

export function AppIcon({ icon, className, title }: AppIconProps) {
  const resolvedIcon = sanitizeIconSlug(icon);
  const fallback = <KeyRoundIcon className={cn('h-4 w-4', className)} aria-hidden={!title} title={title} />;

  return (
    <Suspense fallback={fallback}>
      <IconifyIcon icon={resolvedIcon} className={cn('h-4 w-4', className)} aria-hidden={!title} title={title} />
    </Suspense>
  );
}
