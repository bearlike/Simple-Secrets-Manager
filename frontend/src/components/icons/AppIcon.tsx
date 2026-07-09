import { lazy, Suspense, type SVGProps } from 'react';
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
  // `title` is a valid global DOM attribute (renders a native tooltip) but React
  // types it only on HTMLAttributes, not SVGAttributes; picking just the SVG
  // props we set and adding `title` lets both icon components accept it cleanly.
  const iconProps: Pick<SVGProps<SVGSVGElement>, 'className' | 'aria-hidden'> & {
    title?: string;
  } = {
    className: cn('h-4 w-4', className),
    'aria-hidden': !title,
    title
  };
  const fallback = <KeyRoundIcon {...iconProps} />;

  return (
    <Suspense fallback={fallback}>
      <IconifyIcon icon={resolvedIcon} {...iconProps} />
    </Suspense>
  );
}
