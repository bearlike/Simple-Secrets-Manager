import { useMemo, useState } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getFilteredRowModel,
  flexRender,
  type ColumnDef } from
'@tanstack/react-table';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  EyeIcon,
  EyeOffIcon,
  PencilIcon,
  Trash2Icon,
  PlusIcon,
  SearchIcon } from
'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Popover,
  PopoverContent,
  PopoverTrigger } from
'@/components/ui/popover';
import { getSecrets, deleteSecret } from '../../lib/api/secrets';
import { queryKeys } from '../../lib/api/queryKeys';
import type { Secret } from '../../lib/api/types';
import { AddSecretDialog } from './AddSecretDialog';
import { EditSecretPopover } from './EditSecretPopover';
import { ConfirmDialog } from '../common/ConfirmDialog';
import { EmptyState } from '../common/EmptyState';
function formatRelativeTime(dateStr?: string): string {
  if (!dateStr) return '—';
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) return '—';
  const diff = Date.now() - date.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}
function getConfigBadgeClass(configSlug: string): string {
  if (configSlug === 'dev' || configSlug === 'development')
  return 'bg-green-50 text-green-700 border-green-200';
  if (configSlug === 'staging')
  return 'bg-yellow-50 text-yellow-700 border-yellow-200';
  if (configSlug === 'prod' || configSlug === 'production')
  return 'bg-red-50 text-red-700 border-red-200';
  return 'bg-secondary text-secondary-foreground';
}
interface SecretsTableProps {
  projectSlug: string;
  configSlug: string;
}
export function SecretsTable({ projectSlug, configSlug }: SecretsTableProps) {
  const queryClient = useQueryClient();
  const [revealedKeys, setRevealedKeys] = useState<Set<string>>(new Set());
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [deletingKey, setDeletingKey] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [globalFilter, setGlobalFilter] = useState('');
  const { data: secrets = [], isLoading } = useQuery({
    queryKey: queryKeys.secrets(projectSlug, configSlug),
    queryFn: () => getSecrets(projectSlug, configSlug),
    enabled: !!projectSlug && !!configSlug
  });
  const deleteMutation = useMutation({
    mutationFn: (key: string) => deleteSecret(projectSlug, configSlug, key),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.secrets(projectSlug, configSlug)
      });
      toast.success('Secret deleted');
      setDeletingKey(null);
    },
    onError: () => {
      toast.error('Failed to delete secret');
    }
  });
  const toggleReveal = (key: string) => {
    setRevealedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);else
      next.add(key);
      return next;
    });
  };
  const columns = useMemo<ColumnDef<Secret>[]>(
    () => [
    {
      accessorKey: 'key',
      header: 'KEY',
      cell: ({ row }) =>
      <span className="font-mono text-sm font-medium">
            {row.original.key}
          </span>

    },
    {
      accessorKey: 'value',
      header: 'VALUE',
      cell: ({ row }) => {
        const revealed = revealedKeys.has(row.original.key);
        return (
          <div className="flex items-center gap-2">
              <span className="font-mono text-sm text-muted-foreground">
                {revealed ? row.original.value : '••••••••••••'}
              </span>
              <button
              onClick={() => toggleReveal(row.original.key)}
              className="text-muted-foreground hover:text-foreground transition-colors"
              aria-label={revealed ? 'Hide value' : 'Reveal value'}>

                {revealed ?
              <EyeOffIcon className="h-3.5 w-3.5" /> :

              <EyeIcon className="h-3.5 w-3.5" />
              }
              </button>
            </div>);

      }
    },
    {
      accessorKey: 'updatedAt',
      header: 'UPDATED',
      cell: ({ row }) =>
      <span className="text-xs text-muted-foreground">
            {formatRelativeTime(row.original.updatedAt)}
          </span>

    },
    {
      id: 'actions',
      header: '',
      cell: ({ row }) =>
      <div className="flex items-center gap-1 justify-end">
            <Popover
          open={editingKey === row.original.key}
          onOpenChange={(open) => {
            if (!open) setEditingKey(null);
          }}>

              <PopoverTrigger asChild>
                <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0"
              onClick={() => setEditingKey(row.original.key)}
              aria-label="Edit secret">

                  <PencilIcon className="h-3.5 w-3.5" />
                </Button>
              </PopoverTrigger>
              <PopoverContent side="left" align="start" className="p-0 w-auto">
                <EditSecretPopover
              secret={row.original}
              projectSlug={projectSlug}
              configSlug={configSlug}
              onClose={() => setEditingKey(null)} />

              </PopoverContent>
            </Popover>
            <Button
          variant="ghost"
          size="sm"
          className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
          onClick={() => setDeletingKey(row.original.key)}
          aria-label="Delete secret">

              <Trash2Icon className="h-3.5 w-3.5" />
            </Button>
          </div>

    }],

    [revealedKeys, editingKey, projectSlug, configSlug]
  );
  const table = useReactTable({
    data: secrets,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    state: {
      globalFilter
    },
    onGlobalFilterChange: setGlobalFilter,
    globalFilterFn: (row, _columnId, filterValue: string) =>
    row.original.key.toLowerCase().includes(filterValue.toLowerCase())
  });
  return (
    <div className="space-y-3">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-3">
        <div className="relative flex-1 max-w-xs">
          <SearchIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            placeholder="Filter secrets..."
            value={globalFilter}
            onChange={(e) => setGlobalFilter(e.target.value)}
            className="pl-8 h-8 text-sm" />

        </div>
        <div className="flex items-center gap-2">
          <Badge
            variant="outline"
            className={`text-xs font-mono ${getConfigBadgeClass(configSlug)}`}>

            {configSlug}
          </Badge>
          <Button
            size="sm"
            className="h-8 gap-1.5"
            onClick={() => setAddOpen(true)}>

            <PlusIcon className="h-3.5 w-3.5" />
            Add Secret
          </Button>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-md border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-muted/40 border-b border-border">
              {table.getHeaderGroups().map((hg) =>
              hg.headers.map((header) =>
              <th
                key={header.id}
                className="px-4 py-2.5 text-left text-xs font-medium tracking-wider text-muted-foreground">

                    {flexRender(
                  header.column.columnDef.header,
                  header.getContext()
                )}
                  </th>
              )
              )}
            </tr>
          </thead>
          <tbody>
            {isLoading ?
            Array.from({
              length: 5
            }).map((_, i) =>
            <tr key={i} className="border-b border-border last:border-0">
                  <td className="px-4 py-2.5">
                    <Skeleton className="h-4 w-40" />
                  </td>
                  <td className="px-4 py-2.5">
                    <Skeleton className="h-4 w-32" />
                  </td>
                  <td className="px-4 py-2.5">
                    <Skeleton className="h-4 w-16" />
                  </td>
                  <td className="px-4 py-2.5">
                    <Skeleton className="h-4 w-16 ml-auto" />
                  </td>
                </tr>
            ) :
            table.getRowModel().rows.length === 0 ?
            <tr>
                <td colSpan={4}>
                  <EmptyState
                  title={
                  globalFilter ?
                  'No secrets match your filter' :
                  'No secrets yet'
                  }
                  description={
                  globalFilter ?
                  'Try a different search term' :
                  'Add your first secret to get started'
                  }
                  action={
                  !globalFilter ?
                  <Button size="sm" onClick={() => setAddOpen(true)}>
                          <PlusIcon className="h-3.5 w-3.5 mr-1.5" />
                          Add Secret
                        </Button> :
                  undefined
                  } />

                </td>
              </tr> :

            table.getRowModel().rows.map((row) =>
            <tr
              key={row.id}
              className="border-b border-border last:border-0 hover:bg-muted/20 transition-colors">

                  {row.getVisibleCells().map((cell) =>
              <td key={cell.id} className="px-4 py-2.5">
                      {flexRender(
                  cell.column.columnDef.cell,
                  cell.getContext()
                )}
                    </td>
              )}
                </tr>
            )
            }
          </tbody>
        </table>
      </div>

      <AddSecretDialog
        projectSlug={projectSlug}
        configSlug={configSlug}
        open={addOpen}
        onOpenChange={setAddOpen} />


      <ConfirmDialog
        open={!!deletingKey}
        onOpenChange={(open) => {
          if (!open) setDeletingKey(null);
        }}
        title="Delete Secret"
        description={`Are you sure you want to delete "${deletingKey}"? This action cannot be undone.`}
        onConfirm={() => {
          if (deletingKey) deleteMutation.mutate(deletingKey);
        }}
        loading={deleteMutation.isPending}
        destructive />

    </div>);

}
