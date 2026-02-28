import { useState } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef
} from '@tanstack/react-table';
import { KeyRoundIcon } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { ConfirmDialog } from '../common/ConfirmDialog';
import { EmptyState } from '../common/EmptyState';
import type { Token } from '../../lib/api/types';

function formatDate(dateStr?: string): string {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) return '-';
  return date.toLocaleDateString();
}

function formatRelativeTime(dateStr?: string): string {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) return '-';

  const diff = Date.now() - date.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;

  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;

  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function formatDuration(milliseconds: number): string {
  if (milliseconds <= 0) return 'expired';

  const totalMinutes = Math.floor(milliseconds / 60000);
  const days = Math.floor(totalMinutes / (60 * 24));
  const hours = Math.floor((totalMinutes % (60 * 24)) / 60);
  const minutes = totalMinutes % 60;

  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${Math.max(minutes, 1)}m`;
}

function formatTtl(createdAt?: string, expiresAt?: string): string {
  if (!createdAt || !expiresAt) return '-';

  const created = new Date(createdAt);
  const expires = new Date(expiresAt);
  if (Number.isNaN(created.getTime()) || Number.isNaN(expires.getTime())) return '-';

  return formatDuration(expires.getTime() - created.getTime());
}

interface TokensTableProps {
  tokens: Token[];
  onRevoke: (id: string) => void;
  revoking?: string;
  isLoading?: boolean;
}

export function TokensTable({ tokens, onRevoke, revoking, isLoading }: TokensTableProps) {
  const [confirmId, setConfirmId] = useState<string | null>(null);

  const columns: ColumnDef<Token>[] = [
    {
      accessorKey: 'subject',
      header: 'SUBJECT',
      cell: ({ row }) => <span className="font-medium text-sm">{row.original.subject}</span>
    },
    {
      accessorKey: 'type',
      header: 'TYPE',
      cell: ({ row }) => (
        <Badge
          variant="outline"
          className={
            row.original.type === 'service'
              ? 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-300 dark:border-blue-800 text-xs'
              : 'bg-secondary text-secondary-foreground border-border text-xs'
          }
        >
          {row.original.type}
        </Badge>
      )
    },
    {
      accessorKey: 'scopes',
      header: 'SCOPES',
      cell: ({ row }) => (
        <span className="font-mono text-xs text-muted-foreground">
          {row.original.scopes.length > 0 ? row.original.scopes.join(', ') : '-'}
        </span>
      )
    },
    {
      accessorKey: 'expiresAt',
      header: 'EXPIRES',
      cell: ({ row }) => <span className="text-xs text-muted-foreground">{formatDate(row.original.expiresAt)}</span>
    },
    {
      id: 'ttl',
      header: 'TTL',
      cell: ({ row }) => (
        <span className="font-mono text-xs text-muted-foreground">
          {formatTtl(row.original.createdAt, row.original.expiresAt)}
        </span>
      )
    },
    {
      accessorKey: 'lastUsedAt',
      header: 'LAST USED',
      cell: ({ row }) => (
        <span className="text-xs text-muted-foreground">{formatRelativeTime(row.original.lastUsedAt)}</span>
      )
    },
    {
      id: 'actions',
      header: '',
      cell: ({ row }) => (
        <div className="flex justify-end">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs text-muted-foreground hover:text-destructive"
            onClick={() => setConfirmId(row.original.id)}
            disabled={revoking === row.original.id}
          >
            {revoking === row.original.id ? 'Revoking...' : 'Revoke'}
          </Button>
        </div>
      )
    }
  ];

  const table = useReactTable({
    data: tokens,
    columns,
    getCoreRowModel: getCoreRowModel()
  });

  return (
    <>
      <div className="rounded-md border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-muted/40 border-b border-border">
              {table.getHeaderGroups().map((group) =>
                group.headers.map((header) => (
                  <th
                    key={header.id}
                    className="px-4 py-2.5 text-left text-xs font-medium tracking-wider text-muted-foreground"
                  >
                    {flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))
              )}
            </tr>
          </thead>
          <tbody>
            {isLoading &&
              Array.from({ length: 3 }).map((_, rowIndex) => (
                <tr key={rowIndex} className="border-b border-border last:border-0">
                  {Array.from({ length: 7 }).map((__, colIndex) => (
                    <td key={colIndex} className="px-4 py-2.5">
                      <Skeleton className="h-4 w-20" />
                    </td>
                  ))}
                </tr>
              ))}

            {!isLoading &&
              table.getRowModel().rows.length === 0 && (
                <tr>
                  <td colSpan={7}>
                    <EmptyState
                      icon={KeyRoundIcon}
                      title="No tokens yet"
                      description="Create a token to access the API programmatically"
                    />
                  </td>
                </tr>
              )}

            {!isLoading &&
              table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  className="border-b border-border last:border-0 hover:bg-muted/20 transition-colors"
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-4 py-2.5">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      <ConfirmDialog
        open={!!confirmId}
        onOpenChange={(open) => {
          if (!open) setConfirmId(null);
        }}
        title="Revoke Token"
        description="Are you sure you want to revoke this token? Any services using it will lose access immediately."
        onConfirm={() => {
          if (confirmId) {
            onRevoke(confirmId);
            setConfirmId(null);
          }
        }}
        destructive
      />
    </>
  );
}
