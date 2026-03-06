import { EllipsisIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu';
import type { SecretRowAction } from './types';

interface SecretRowActionsProps {
  actions: SecretRowAction[];
  rowLabel: string;
}

export function SecretRowActions({ actions, rowLabel }: SecretRowActionsProps) {
  return (
    <>
      <div className="hidden items-center justify-end gap-1 lg:flex">
        {actions.map((action) => (
          <Button
            key={action.key}
            variant="ghost"
            size="sm"
            className={`h-7 w-7 p-0 ${action.destructive ? 'text-muted-foreground hover:text-destructive' : ''}`}
            onClick={action.onSelect}
            disabled={action.disabled}
            aria-label={action.label}
          >
            <action.icon className="h-3.5 w-3.5" />
          </Button>
        ))}
      </div>
      <div className="flex justify-end lg:hidden">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="sm" className="h-7 w-7 p-0" aria-label={`Open actions for ${rowLabel}`}>
              <EllipsisIcon className="h-3.5 w-3.5" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            {actions.map((action) => (
              <DropdownMenuItem
                key={action.key}
                onClick={action.onSelect}
                disabled={action.disabled}
                className={action.destructive ? 'text-destructive focus:text-destructive' : ''}
              >
                <action.icon className="mr-2 h-3.5 w-3.5" />
                {action.label}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </>
  );
}
