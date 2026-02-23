import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
}
export function EmptyState({
  icon: Icon,
  title,
  description,
  action
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      {Icon &&
      <div className="mb-4 rounded-full bg-muted p-4">
          <Icon className="h-8 w-8 text-muted-foreground" />
        </div>
      }
      <h3 className="text-sm font-medium text-foreground">{title}</h3>
      {description &&
      <p className="mt-1 text-sm text-muted-foreground max-w-sm">
          {description}
        </p>
      }
      {action && <div className="mt-4">{action}</div>}
    </div>);

}
