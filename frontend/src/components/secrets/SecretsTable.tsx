import { useMemo, useRef, useState, type ChangeEventHandler } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getFilteredRowModel,
  flexRender,
  type ColumnDef
} from '@tanstack/react-table';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  EyeIcon,
  EyeOffIcon,
  PencilIcon,
  PlusIcon,
  SearchIcon,
  Trash2Icon,
  UploadIcon
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import {
  deleteSecret,
  getSecrets,
  getSecretsKeyMap,
  type SecretUpsertInput,
  upsertSecretsBulk
} from '../../lib/api/secrets';
import { parseEnvContent } from '../../lib/env';
import { queryKeys } from '../../lib/api/queryKeys';
import type { Secret } from '../../lib/api/types';
import { AddSecretDialog } from './AddSecretDialog';
import {
  type EnvImportAction,
  type EnvImportPreview,
  type EnvImportPreviewItem,
  ImportEnvDialog
} from './ImportEnvDialog';
import { EditSecretPopover } from './EditSecretPopover';
import { ConfirmDialog } from '../common/ConfirmDialog';
import { EmptyState } from '../common/EmptyState';
import { getConfigBadgeClass } from '../../lib/badgeStyles';

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

function hasOwnKey(record: Record<string, string>, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(record, key);
}

interface SecretsTableProps {
  projectSlug: string;
  configSlug: string;
}

export function SecretsTable({ projectSlug, configSlug }: SecretsTableProps) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [revealedKeys, setRevealedKeys] = useState<Set<string>>(new Set());
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [deletingKey, setDeletingKey] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [globalFilter, setGlobalFilter] = useState('');
  const [importOpen, setImportOpen] = useState(false);
  const [importPreview, setImportPreview] = useState<EnvImportPreview | null>(null);

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

  const importMutation = useMutation({
    mutationFn: async () => {
      if (!importPreview) {
        return { succeeded: 0, failedKeys: [] as string[] };
      }

      const entries: SecretUpsertInput[] = importPreview.items.map((item) => ({
        key: item.key,
        value: item.value
      }));
      return upsertSecretsBulk(projectSlug, configSlug, entries);
    },
    onSuccess: ({ succeeded, failedKeys }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.secrets(projectSlug, configSlug)
      });
      setImportOpen(false);
      setImportPreview(null);

      if (failedKeys.length === 0) {
        toast.success(`Imported ${succeeded} variable${succeeded === 1 ? '' : 's'}`);
        return;
      }

      const failedPreview = failedKeys.slice(0, 3).join(', ');
      const moreFailed = failedKeys.length > 3 ? ', ...' : '';
      toast.error(
        `Imported ${succeeded} variable${succeeded === 1 ? '' : 's'}; failed ${failedKeys.length}` +
          (failedPreview ? ` (${failedPreview}${moreFailed})` : '')
      );
    },
    onError: (error) => {
      const message = error instanceof Error ? error.message : 'Failed to import .env file';
      toast.error(message);
    }
  });

  const toggleReveal = (key: string) => {
    setRevealedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const buildPreview = async (file: File) => {
    const content = await file.text();
    const parsed = parseEnvContent(content);

    if (parsed.errors.length > 0) {
      const shownErrors = parsed.errors.slice(0, 2).join('; ');
      const more = parsed.errors.length > 2 ? ' ...' : '';
      toast.error(`Invalid .env file: ${shownErrors}${more}`);
      return;
    }

    if (parsed.entries.length === 0) {
      toast.error('No environment variables found in file');
      return;
    }

    const [effectiveSecrets, directSecrets] = await Promise.all([
      getSecretsKeyMap(projectSlug, configSlug, true),
      getSecretsKeyMap(projectSlug, configSlug, false)
    ]);

    const items: EnvImportPreviewItem[] = parsed.entries.map((entry) => {
      let action: EnvImportAction = 'create';
      if (hasOwnKey(directSecrets, entry.key)) {
        action = 'overwrite';
      } else if (hasOwnKey(effectiveSecrets, entry.key)) {
        action = 'override_inherited';
      }

      return {
        key: entry.key,
        value: entry.value,
        action,
        hasReference: entry.hasReference
      };
    });

    const counts = items.reduce(
      (acc, item) => {
        if (item.action === 'create') acc.createCount += 1;
        if (item.action === 'overwrite') acc.overwriteCount += 1;
        if (item.action === 'override_inherited') acc.overrideInheritedCount += 1;
        return acc;
      },
      {
        createCount: 0,
        overwriteCount: 0,
        overrideInheritedCount: 0
      }
    );

    setImportPreview({
      fileName: file.name || '.env',
      total: items.length,
      duplicateCount: parsed.duplicateCount,
      createCount: counts.createCount,
      overwriteCount: counts.overwriteCount,
      overrideInheritedCount: counts.overrideInheritedCount,
      items
    });
    setImportOpen(true);
  };

  const onFileChange: ChangeEventHandler<HTMLInputElement> = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;

    try {
      await buildPreview(file);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to read .env file';
      toast.error(message);
    }
  };

  const columns = useMemo<ColumnDef<Secret>[]>(
    () => [
      {
        accessorKey: 'key',
        header: 'KEY',
        cell: ({ row }) => <span className="font-mono text-sm font-medium">{row.original.key}</span>
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
                aria-label={revealed ? 'Hide value' : 'Reveal value'}
              >
                {revealed ? <EyeOffIcon className="h-3.5 w-3.5" /> : <EyeIcon className="h-3.5 w-3.5" />}
              </button>
            </div>
          );
        }
      },
      {
        accessorKey: 'updatedAt',
        header: 'UPDATED',
        cell: ({ row }) => (
          <span className="text-xs text-muted-foreground">{formatRelativeTime(row.original.updatedAt)}</span>
        )
      },
      {
        id: 'actions',
        header: '',
        cell: ({ row }) => (
          <div className="flex items-center gap-1 justify-end">
            <Popover
              open={editingKey === row.original.key}
              onOpenChange={(open) => {
                if (!open) setEditingKey(null);
              }}
            >
              <PopoverTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 w-7 p-0"
                  onClick={() => setEditingKey(row.original.key)}
                  aria-label="Edit secret"
                >
                  <PencilIcon className="h-3.5 w-3.5" />
                </Button>
              </PopoverTrigger>
              <PopoverContent side="left" align="start" className="p-0 w-auto">
                <EditSecretPopover
                  secret={row.original}
                  projectSlug={projectSlug}
                  configSlug={configSlug}
                  onClose={() => setEditingKey(null)}
                />
              </PopoverContent>
            </Popover>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
              onClick={() => setDeletingKey(row.original.key)}
              aria-label="Delete secret"
            >
              <Trash2Icon className="h-3.5 w-3.5" />
            </Button>
          </div>
        )
      }
    ],
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
      <div className="flex items-center justify-between gap-3">
        <div className="relative flex-1 max-w-xs">
          <SearchIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            placeholder="Filter secrets..."
            value={globalFilter}
            onChange={(event) => setGlobalFilter(event.target.value)}
            className="pl-8 h-8 text-sm"
          />
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className={`text-xs font-mono ${getConfigBadgeClass(configSlug)}`}>
            {configSlug}
          </Badge>
          <Button
            variant="outline"
            size="sm"
            className="h-8 gap-1.5"
            onClick={() => fileInputRef.current?.click()}
          >
            <UploadIcon className="h-3.5 w-3.5" />
            Import .env
          </Button>
          <Button size="sm" className="h-8 gap-1.5" onClick={() => setAddOpen(true)}>
            <PlusIcon className="h-3.5 w-3.5" />
            Add Secret
          </Button>
        </div>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept=".env,text/plain"
        className="hidden"
        onChange={onFileChange}
      />

      <div className="rounded-md border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-muted/40 border-b border-border">
              {table.getHeaderGroups().map((headerGroup) =>
                headerGroup.headers.map((header) => (
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
            {isLoading
              ? Array.from({ length: 5 }).map((_, index) => (
                  <tr key={index} className="border-b border-border last:border-0">
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
                ))
              : table.getRowModel().rows.length === 0
                ? (
                    <tr>
                      <td colSpan={4}>
                        <EmptyState
                          title={globalFilter ? 'No secrets match your filter' : 'No secrets yet'}
                          description={
                            globalFilter ? 'Try a different search term' : 'Add your first secret to get started'
                          }
                          action={
                            !globalFilter ? (
                              <Button size="sm" onClick={() => setAddOpen(true)}>
                                <PlusIcon className="h-3.5 w-3.5 mr-1.5" />
                                Add Secret
                              </Button>
                            ) : undefined
                          }
                        />
                      </td>
                    </tr>
                  )
                : table.getRowModel().rows.map((row) => (
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

      <AddSecretDialog
        projectSlug={projectSlug}
        configSlug={configSlug}
        open={addOpen}
        onOpenChange={setAddOpen}
      />

      <ImportEnvDialog
        open={importOpen}
        onOpenChange={(open) => {
          setImportOpen(open);
          if (!open && !importMutation.isPending) {
            setImportPreview(null);
          }
        }}
        preview={importPreview}
        loading={importMutation.isPending}
        onConfirm={() => importMutation.mutate()}
      />

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
        destructive
      />
    </div>
  );
}
