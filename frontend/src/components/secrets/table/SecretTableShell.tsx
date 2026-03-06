import type { ReactNode } from 'react';
import { Table, TableCaption } from '@/components/ui/table';
import { cn } from '@/lib/utils';

interface SecretTableShellProps {
  caption: string;
  children: ReactNode;
  minWidthClassName?: string;
  className?: string;
  tableClassName?: string;
}

export function SecretTableShell({
  caption,
  children,
  minWidthClassName = 'min-w-[760px]',
  className,
  tableClassName
}: SecretTableShellProps) {
  return (
    <div className={cn('rounded-md border border-border ssm-table-scroll', className)}>
      <Table className={cn('w-full table-fixed text-sm', minWidthClassName, tableClassName)}>
        <TableCaption className="sr-only">{caption}</TableCaption>
        {children}
      </Table>
    </div>
  );
}
