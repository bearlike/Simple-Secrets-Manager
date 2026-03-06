import { useEffect, useMemo, useRef, useState, type ChangeEventHandler } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getFilteredRowModel,
  flexRender,
  type ColumnDef,
  type Row
} from '@tanstack/react-table';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';
import {
  ChevronDownIcon,
  ChevronRightIcon,
  EyeIcon,
  EyeOffIcon,
  GitCompareArrowsIcon,
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
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
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
import { EditSecretDialog } from './EditSecretDialog';
import { SecretRowActions } from './table/SecretRowActions';
import { SecretTableShell } from './table/SecretTableShell';
import { SecretValueRevealCell } from './table/SecretValueRevealCell';
import type { SecretRowAction } from './table/types';
import { ConfirmDialog } from '../common/ConfirmDialog';
import { EmptyState } from '../common/EmptyState';
import { getConfigBadgeClass } from '../../lib/badgeStyles';
import { AppIcon } from '../icons/AppIcon';
import { notifyApiError } from '../../lib/api/errorToast';

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

type ForkBucket = 'override' | 'inherited';

interface SecretRow extends Secret {
  forkBucket: ForkBucket;
  isDirectInConfig: boolean;
}

export interface ForkSecretsSummary {
  isFork: boolean;
  overrides: number;
  inherited: number;
  parentComparisonDegraded: boolean;
}

interface SecretsQueryData {
  rows: SecretRow[];
  summary: ForkSecretsSummary;
}

interface SecretsTableProps {
  projectSlug: string;
  configSlug: string;
  parentSlug?: string;
  onForkSummaryChange?: (summary: ForkSecretsSummary) => void;
}

const COLUMN_CLASS: Record<string, { header: string; cell: string }> = {
  icon: { header: 'w-10 sm:w-12', cell: 'w-10 sm:w-12 align-top' },
  key: {
    header: 'w-[10rem] sm:w-[12rem]',
    cell: 'w-[10rem] sm:w-[12rem] align-top'
  },
  value: {
    header: 'w-[18rem] sm:w-[22rem] xl:w-[26rem]',
    cell: 'w-[18rem] sm:w-[22rem] xl:w-[26rem] align-top'
  },
  updatedAt: {
    header: 'w-[6.5rem] whitespace-nowrap',
    cell: 'w-[6.5rem] whitespace-nowrap align-top'
  },
  actions: {
    header: 'w-10 sm:w-12 lg:w-40 text-right',
    cell: 'w-10 sm:w-12 lg:w-40 align-top'
  }
};

function columnClass(columnId: string, header = false): string {
  const classes = COLUMN_CLASS[columnId];
  if (!classes) return header ? '' : 'align-top';
  return header ? classes.header : classes.cell;
}

function summarizeForkRows(
  rows: SecretRow[],
  isFork: boolean,
  parentComparisonDegraded = false
): ForkSecretsSummary {
  if (!isFork) {
    return {
      isFork: false,
      overrides: rows.length,
      inherited: 0,
      parentComparisonDegraded: false
    };
  }

  const overrides = rows.filter((row) => row.forkBucket === 'override').length;
  return {
    isFork: true,
    overrides,
    inherited: rows.length - overrides,
    parentComparisonDegraded
  };
}

export function SecretsTable({
  projectSlug,
  configSlug,
  parentSlug,
  onForkSummaryChange
}: SecretsTableProps) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [revealedKeys, setRevealedKeys] = useState<Set<string>>(new Set());
  const [editingSecret, setEditingSecret] = useState<Secret | null>(null);
  const [deletingKey, setDeletingKey] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [globalFilter, setGlobalFilter] = useState('');
  const [importOpen, setImportOpen] = useState(false);
  const [importPreview, setImportPreview] = useState<EnvImportPreview | null>(null);
  const [overridesOpen, setOverridesOpen] = useState(true);
  const [inheritedOpen, setInheritedOpen] = useState(false);

  const isFork = Boolean(parentSlug);

  useEffect(() => {
    setOverridesOpen(true);
    setInheritedOpen(false);
  }, [projectSlug, configSlug, parentSlug]);

  const { data: secretsData, isLoading } = useQuery<SecretsQueryData>({
    queryKey: queryKeys.secretsView(projectSlug, configSlug, parentSlug),
    queryFn: async () => {
      const effectiveSecrets = await getSecrets(projectSlug, configSlug, {
        includeParent: true,
        includeMeta: true,
        resolveReferences: false,
        raw: false
      });

      if (!parentSlug) {
        const rows: SecretRow[] = effectiveSecrets.map((secret) => ({
          ...secret,
          forkBucket: 'override',
          isDirectInConfig: true
        }));
        return {
          rows,
          summary: summarizeForkRows(rows, false)
        };
      }

      const [directSecrets, parentSecretsResult] = await Promise.all([
        getSecretsKeyMap(projectSlug, configSlug, false, {
          includeParent: false,
          includeMeta: false,
          resolveReferences: false,
          raw: false
        }),
        getSecretsKeyMap(projectSlug, parentSlug, true, {
          includeParent: true,
          includeMeta: false,
          resolveReferences: false,
          raw: false
        })
          .then((data) => ({ data, failed: false }))
          .catch(() => ({ data: {} as Record<string, string>, failed: true }))
      ]);

      const parentSecrets = parentSecretsResult.data;
      const parentComparisonDegraded = parentSecretsResult.failed;

      const rows: SecretRow[] = effectiveSecrets.map((secret) => {
        const isDirectInConfig = hasOwnKey(directSecrets, secret.key);

        let forkBucket: ForkBucket = 'inherited';
        if (isDirectInConfig) {
          if (parentComparisonDegraded) {
            forkBucket = 'override';
          } else if (!hasOwnKey(parentSecrets, secret.key)) {
            forkBucket = 'override';
          } else {
            forkBucket = directSecrets[secret.key] === parentSecrets[secret.key] ? 'inherited' : 'override';
          }
        }

        return {
          ...secret,
          forkBucket,
          isDirectInConfig
        };
      });

      return {
        rows,
        summary: summarizeForkRows(rows, true, parentComparisonDegraded)
      };
    },
    enabled: !!projectSlug && !!configSlug
  });

  useEffect(() => {
    if (!onForkSummaryChange || !secretsData) return;
    onForkSummaryChange(secretsData.summary);
  }, [onForkSummaryChange, secretsData]);

  const secrets = useMemo(() => secretsData?.rows ?? [], [secretsData?.rows]);
  const summary = secretsData?.summary;

  const deleteMutation = useMutation({
    mutationFn: (key: string) => deleteSecret(projectSlug, configSlug, key),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.secrets(projectSlug, configSlug)
      });
      toast.success('Secret deleted');
      setDeletingKey(null);
    },
    onError: (error) => {
      notifyApiError(error, 'Failed to delete secret');
    }
  });

  const importMutation = useMutation({
    mutationFn: async () => {
      if (!importPreview) {
        return { succeeded: 0, failed: [] as { key: string; message: string }[] };
      }

      const entries: SecretUpsertInput[] = importPreview.items.map((item) => ({
        key: item.key,
        value: item.value
      }));
      return upsertSecretsBulk(projectSlug, configSlug, entries);
    },
    onSuccess: ({ succeeded, failed }) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.secrets(projectSlug, configSlug)
      });
      setImportOpen(false);
      setImportPreview(null);

      if (failed.length === 0) {
        toast.success(`Imported ${succeeded} variable${succeeded === 1 ? '' : 's'}`);
        return;
      }

      const failedPreview = failed.slice(0, 3).map((item) => item.key).join(', ');
      const moreFailed = failed.length > 3 ? ', ...' : '';
      const firstError = failed[0]?.message ? `: ${failed[0].message}` : '';
      toast.error(
        `Imported ${succeeded} variable${succeeded === 1 ? '' : 's'}; failed ${failed.length}` +
          (failedPreview ? ` (${failedPreview}${moreFailed})` : '') +
          firstError
      );
    },
    onError: (error) => {
      notifyApiError(error, 'Failed to import .env file');
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
      notifyApiError(error, 'Failed to read .env file');
    }
  };

  const columns = useMemo<ColumnDef<SecretRow>[]>(
    () => [
      {
        id: 'icon',
        header: '',
        cell: ({ row }) => (
          <div className="flex h-full min-h-8 items-center justify-center">
            <AppIcon icon={row.original.iconSlug} className="h-full w-full max-h-8 max-w-8 text-muted-foreground" />
          </div>
        )
      },
      {
        accessorKey: 'key',
        header: 'KEY',
        cell: ({ row }) => {
          const inherited = row.original.forkBucket === 'inherited';
          return (
            <span
              className={`block max-w-full break-all font-mono text-sm font-medium leading-5 ${
                inherited ? 'text-muted-foreground' : ''
              }`}
            >
              {row.original.key}
            </span>
          );
        }
      },
      {
        accessorKey: 'value',
        header: 'VALUE',
        cell: ({ row }) => {
          const revealed = revealedKeys.has(row.original.key);
          const inherited = row.original.forkBucket === 'inherited';
          return (
            <SecretValueRevealCell
              value={row.original.value}
              revealed={revealed}
              tone={inherited ? 'inherited' : 'default'}
            />
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
        cell: ({ row }) => {
          const isInherited = row.original.forkBucket === 'inherited';
          const editLabel = isInherited ? 'Override inherited secret' : 'Edit secret';
          const isRevealed = revealedKeys.has(row.original.key);
          const rowActions: SecretRowAction[] = [
            {
              key: 'toggle-visibility',
              label: isRevealed ? 'Hide value' : 'Reveal value',
              onSelect: () => toggleReveal(row.original.key),
              icon: isRevealed ? EyeOffIcon : EyeIcon
            },
            {
              key: 'compare',
              label: 'Compare secret',
              onSelect: () =>
                navigate(`/projects/${projectSlug}/compare/secret?key=${encodeURIComponent(row.original.key)}`),
              icon: GitCompareArrowsIcon
            },
            {
              key: 'edit',
              label: editLabel,
              onSelect: () => setEditingSecret(row.original),
              icon: PencilIcon
            },
            {
              key: 'delete',
              label: 'Delete secret',
              onSelect: () => setDeletingKey(row.original.key),
              icon: Trash2Icon,
              destructive: true
            }
          ];
          return <SecretRowActions actions={rowActions} rowLabel={row.original.key} />;
        }
      }
    ],
    [navigate, projectSlug, revealedKeys]
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

  const filteredRows = table.getRowModel().rows;
  const overrideRows = isFork ? filteredRows.filter((row) => row.original.forkBucket === 'override') : filteredRows;
  const inheritedRows = isFork ? filteredRows.filter((row) => row.original.forkBucket === 'inherited') : [];

  const renderDataRow = (row: Row<SecretRow>) => {
    const inherited = row.original.forkBucket === 'inherited';
    return (
      <TableRow
        key={row.id}
        className={`border-b border-border last:border-0 transition-colors ${
          inherited ? 'bg-muted/10 hover:bg-muted/20' : 'hover:bg-muted/20'
        }`}
      >
        {row.getVisibleCells().map((cell) => (
          <TableCell
            key={cell.id}
            className={`py-2 ${cell.column.id === 'icon' ? 'px-2' : 'px-2.5 sm:px-3 lg:px-4'} ${columnClass(
              cell.column.id
            )}`}
          >
            {flexRender(cell.column.columnDef.cell, cell.getContext())}
          </TableCell>
        ))}
      </TableRow>
    );
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 sm:gap-3">
        <div className="relative order-2 min-w-0 flex-1 basis-full sm:order-1 sm:basis-auto">
          <SearchIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            placeholder="Filter secrets..."
            value={globalFilter}
            onChange={(event) => setGlobalFilter(event.target.value)}
            className="h-8 pl-8 text-sm"
          />
        </div>
        <div className="order-1 ml-auto flex shrink-0 items-center gap-1 sm:order-2 sm:gap-2">
          <Badge
            variant="outline"
            className={`hidden text-xs font-mono md:inline-flex ${getConfigBadgeClass(configSlug)}`}
          >
            {configSlug}
          </Badge>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0 lg:h-8 lg:w-auto lg:gap-1.5 lg:px-3"
                onClick={() => fileInputRef.current?.click()}
                aria-label="Import .env"
              >
                <UploadIcon className="h-3.5 w-3.5" />
                <span className="hidden lg:inline">Import .env</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent className="lg:hidden">Import .env</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                size="sm"
                className="h-8 w-8 p-0 lg:h-8 lg:w-auto lg:gap-1.5 lg:px-3"
                onClick={() => setAddOpen(true)}
                aria-label="Add Secret"
              >
                <PlusIcon className="h-3.5 w-3.5" />
                <span className="hidden lg:inline">Add Secret</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent className="lg:hidden">Add Secret</TooltipContent>
          </Tooltip>
        </div>
      </div>

      {isFork && summary?.parentComparisonDegraded && (
        <p className="text-xs text-muted-foreground">
          Parent diff comparison is partially unavailable; direct keys are treated as overrides.
        </p>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept=".env,text/plain"
        className="hidden"
        onChange={onFileChange}
      />

      <p className="px-0.5 text-[11px] text-muted-foreground xl:hidden">
        Swipe or scroll horizontally to view all columns.
      </p>
      <SecretTableShell caption="Environment secrets table with columns key, value, updated time, and actions.">
        <TableHeader>
          <TableRow className="bg-muted/40 border-b border-border hover:bg-muted/40">
            {table.getHeaderGroups().map((headerGroup) =>
              headerGroup.headers.map((header) => (
                <TableHead
                  key={header.id}
                  scope="col"
                  className={`h-auto py-2 text-left text-xs font-medium tracking-wider text-muted-foreground ${
                    header.column.id === 'icon' ? 'px-2' : 'px-2.5 sm:px-3 lg:px-4'
                  } ${columnClass(header.column.id, true)}`}
                >
                  {flexRender(header.column.columnDef.header, header.getContext())}
                </TableHead>
              ))
            )}
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading ? (
            Array.from({ length: 5 }).map((_, index) => (
              <TableRow key={index} className="border-b border-border last:border-0">
                <TableCell className="px-2 py-2">
                  <Skeleton className="h-8 w-8 rounded-md" />
                </TableCell>
                <TableCell className="px-2.5 py-2 sm:px-3 lg:px-4">
                  <Skeleton className="h-4 w-40" />
                </TableCell>
                <TableCell className="px-2.5 py-2 sm:px-3 lg:px-4">
                  <Skeleton className="h-4 w-32" />
                </TableCell>
                <TableCell className="px-2.5 py-2 sm:px-3 lg:px-4">
                  <Skeleton className="h-4 w-16" />
                </TableCell>
                <TableCell className="px-2.5 py-2 sm:px-3 lg:px-4">
                  <Skeleton className="h-4 w-16 ml-auto" />
                </TableCell>
              </TableRow>
            ))
          ) : filteredRows.length === 0 ? (
            <TableRow>
              <TableCell colSpan={5}>
                <EmptyState
                  title={globalFilter ? 'No secrets match your filter' : 'No secrets yet'}
                  description={globalFilter ? 'Try a different search term' : 'Add your first secret to get started'}
                  action={
                    !globalFilter ? (
                      <Button size="sm" onClick={() => setAddOpen(true)}>
                        <PlusIcon className="h-3.5 w-3.5 mr-1.5" />
                        Add Secret
                      </Button>
                    ) : undefined
                  }
                />
              </TableCell>
            </TableRow>
          ) : isFork ? (
            <>
              <TableRow className="border-b border-border bg-muted/20 hover:bg-muted/20">
                <TableCell colSpan={5} className="px-2 py-1.5">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 gap-1.5 px-2 text-xs"
                    onClick={() => setOverridesOpen((open) => !open)}
                    aria-expanded={overridesOpen}
                  >
                    {overridesOpen ? <ChevronDownIcon className="h-3.5 w-3.5" /> : <ChevronRightIcon className="h-3.5 w-3.5" />}
                    Overrides
                    <Badge variant="outline" className="text-[10px] font-mono">
                      {overrideRows.length}
                    </Badge>
                  </Button>
                </TableCell>
              </TableRow>
              {overridesOpen &&
                (overrideRows.length > 0 ? (
                  overrideRows.map((row) => renderDataRow(row))
                ) : (
                  <TableRow className="border-b border-border last:border-0 hover:bg-transparent">
                    <TableCell colSpan={5} className="px-2.5 py-3 text-xs text-muted-foreground sm:px-3 lg:px-4">
                      No overrides in this view.
                    </TableCell>
                  </TableRow>
                ))}

              <TableRow className="border-b border-border bg-muted/30 hover:bg-muted/30">
                <TableCell colSpan={5} className="px-2 py-1.5">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 gap-1.5 px-2 text-xs text-muted-foreground"
                    onClick={() => setInheritedOpen((open) => !open)}
                    aria-expanded={inheritedOpen}
                  >
                    {inheritedOpen ? <ChevronDownIcon className="h-3.5 w-3.5" /> : <ChevronRightIcon className="h-3.5 w-3.5" />}
                    Inherited
                    <Badge variant="outline" className="text-[10px] font-mono">
                      {inheritedRows.length}
                    </Badge>
                  </Button>
                </TableCell>
              </TableRow>
              {inheritedOpen &&
                (inheritedRows.length > 0 ? (
                  inheritedRows.map((row) => renderDataRow(row))
                ) : (
                  <TableRow className="border-b border-border last:border-0 hover:bg-transparent">
                    <TableCell colSpan={5} className="px-2.5 py-3 text-xs text-muted-foreground sm:px-3 lg:px-4">
                      No inherited secrets in this view.
                    </TableCell>
                  </TableRow>
                ))}
            </>
          ) : (
            filteredRows.map((row) => renderDataRow(row))
          )}
        </TableBody>
      </SecretTableShell>

      <AddSecretDialog
        projectSlug={projectSlug}
        configSlug={configSlug}
        open={addOpen}
        onOpenChange={setAddOpen}
      />

      <EditSecretDialog
        secret={editingSecret}
        projectSlug={projectSlug}
        configSlug={configSlug}
        open={!!editingSecret}
        onOpenChange={(open) => {
          if (!open) setEditingSecret(null);
        }}
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
