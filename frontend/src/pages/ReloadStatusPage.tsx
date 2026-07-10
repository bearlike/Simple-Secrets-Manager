import { useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { RefreshCwIcon, XIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select';
import { getReloadStatus } from '../lib/api/reload';
import { getProjects } from '../lib/api/projects';
import { getConfigs } from '../lib/api/configs';
import { queryKeys } from '../lib/api/queryKeys';
import { EmptyState } from '../components/common/EmptyState';
import { formatAbsolute, formatRelativeTime } from '../lib/time';
import { outcomeBadgeClass, type OutcomeKind } from '../lib/badgeStyles';
import type {
  ReloadInstanceOutcome,
  ReloadInstanceStatus,
  ReloadUnitOutcome
} from '../lib/api/types';

const RELOAD_STATUS_REFETCH_INTERVAL_MS = 30000;
// Reloaders report every ~30s; anything older than 4x that interval is
// treated as stale (missed a couple of check-ins, not just mid-cycle).
const STALE_THRESHOLD_MS = 2 * 60 * 1000;

const INSTANCE_OUTCOME_KIND: Record<ReloadInstanceOutcome, OutcomeKind> = {
  current: 'success',
  updated: 'info',
  error: 'error'
};

const UNIT_OUTCOME_KIND: Record<ReloadUnitOutcome, OutcomeKind> = {
  current: 'success',
  recreated: 'info',
  failed: 'error',
  skipped: 'neutral'
};

interface FleetRow {
  key: string;
  project: string;
  config: string;
  instance: ReloadInstanceStatus;
}

function isStale(lastSeenAt: string): boolean {
  const seenAtMs = new Date(lastSeenAt).getTime();
  if (Number.isNaN(seenAtMs)) return false;
  return Date.now() - seenAtMs > STALE_THRESHOLD_MS;
}

function shortenRevision(revision: string | null): string {
  if (!revision) return '-';
  const stripped = revision.replace(/^"|"$/g, '');
  return stripped.length > 12 ? `${stripped.slice(0, 12)}...` : stripped;
}

function shortenInstanceId(instanceId: string): string {
  return instanceId.length > 8 ? instanceId.slice(-8) : instanceId;
}

export function ReloadStatusPage() {
  // The URL is the single source of truth for the filters, so
  // /reload?project=vpn&config=zurich is a deterministic, bookmarkable view --
  // and ConfigUsageDialog can deep-link straight into one config's fleet.
  const [searchParams, setSearchParams] = useSearchParams();
  const projectFilter = searchParams.get('project') ?? '';
  const configFilter = searchParams.get('config') ?? '';

  // A config slug is only meaningful under its project, so selecting a project
  // always clears the config; `replace` keeps filter churn out of history.
  const applyFilters = (project: string, config: string) => {
    const next: Record<string, string> = {};
    if (project) next.project = project;
    if (project && config) next.config = config;
    setSearchParams(next, { replace: true });
  };

  const { data: projects = [] } = useQuery({
    queryKey: queryKeys.projects(),
    queryFn: getProjects
  });

  const { data: configs = [] } = useQuery({
    queryKey: queryKeys.configs(projectFilter),
    queryFn: () => getConfigs(projectFilter),
    enabled: !!projectFilter
  });

  const { data: configStatuses = [], isLoading, isFetching } = useQuery({
    queryKey: queryKeys.reloadStatus({
      projectSlug: projectFilter || undefined,
      configSlug: configFilter || undefined
    }),
    queryFn: () =>
      getReloadStatus({
        projectSlug: projectFilter || undefined,
        configSlug: configFilter || undefined
      }),
    refetchInterval: RELOAD_STATUS_REFETCH_INTERVAL_MS
  });

  const rows = useMemo<FleetRow[]>(
    () =>
      configStatuses.flatMap((configStatus) =>
        configStatus.instances.map((instance) => ({
          key: `${configStatus.project}:${configStatus.config}:${instance.instanceId}`,
          project: configStatus.project,
          config: configStatus.config,
          instance
        }))
      ),
    [configStatuses]
  );

  const hasFilters = Boolean(projectFilter || configFilter);

  const clearFilters = () => applyFilters('', '');

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-lg font-semibold">Reloader Fleet</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Live status reported by ssm-reload instances watching your configs
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2 mb-4">
        <Select
          value={projectFilter || 'all'}
          onValueChange={(value) => applyFilters(value === 'all' ? '' : value, '')}
        >
          <SelectTrigger className="h-8 w-40 text-xs">
            <SelectValue placeholder="All projects" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All projects</SelectItem>
            {projects.map((project) => (
              <SelectItem key={project.slug} value={project.slug}>
                {project.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {projectFilter && (
          <Select
            value={configFilter || 'all'}
            onValueChange={(value) =>
              applyFilters(projectFilter, value === 'all' ? '' : value)
            }
          >
            <SelectTrigger className="h-8 w-36 text-xs">
              <SelectValue placeholder="All configs" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All configs</SelectItem>
              {configs.map((config) => (
                <SelectItem key={config.slug} value={config.slug}>
                  {config.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        {hasFilters && (
          <Button variant="ghost" size="sm" className="h-8 gap-1.5 text-xs" onClick={clearFilters}>
            <XIcon className="h-3 w-3" />
            Clear
          </Button>
        )}

        {isFetching && !isLoading && (
          <span className="text-xs text-muted-foreground">Refreshing...</span>
        )}
      </div>

      <div className="rounded-md border border-border">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1080px] text-sm">
            <thead>
              <tr className="bg-muted/40 border-b border-border">
                <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider text-muted-foreground">
                  PROJECT
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider text-muted-foreground">
                  CONFIG
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider text-muted-foreground">
                  INSTANCE
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider text-muted-foreground">
                  LAST SEEN
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider text-muted-foreground">
                  LAST RELOADED
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider text-muted-foreground">
                  TRIGGER
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider text-muted-foreground">
                  REVISION
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider text-muted-foreground">
                  OUTCOME
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider text-muted-foreground">
                  UNITS
                </th>
              </tr>
            </thead>
            <tbody>
              {isLoading &&
                Array.from({ length: 6 }).map((_, rowIndex) => (
                  <tr key={rowIndex} className="border-b border-border last:border-0">
                    {Array.from({ length: 9 }).map((__, colIndex) => (
                      <td key={colIndex} className="px-4 py-2">
                        <Skeleton className="h-3.5 w-20" />
                      </td>
                    ))}
                  </tr>
                ))}

              {!isLoading && rows.length === 0 && (
                <tr>
                  <td colSpan={9}>
                    <EmptyState
                      icon={RefreshCwIcon}
                      title="No reloader has reported yet"
                      description={
                        hasFilters
                          ? 'No reloader instances match your filters'
                          : 'The ssm-reload sidecar ships as an optional Docker Compose profile — start it (docker compose --profile reload up -d) to see fleet status here.'
                      }
                    />
                  </td>
                </tr>
              )}

              {!isLoading &&
                rows.map((row) => {
                  const stale = isStale(row.instance.lastSeenAt);
                  return (
                    <tr
                      key={row.key}
                      className="border-b border-border last:border-0 hover:bg-muted/20 transition-colors align-top"
                    >
                      <td className="px-4 py-2">
                        <span className="font-mono text-xs text-muted-foreground">{row.project}</span>
                      </td>
                      <td className="px-4 py-2">
                        <span className="font-mono text-xs text-muted-foreground">{row.config}</span>
                      </td>
                      <td className="px-4 py-2">
                        <div className="flex flex-col">
                          <span className="text-xs font-medium">{row.instance.host}</span>
                          <span className="font-mono text-[10px] text-muted-foreground">
                            #{shortenInstanceId(row.instance.instanceId)}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-2">
                        <div className="flex items-center gap-1.5 whitespace-nowrap">
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span className="text-xs text-muted-foreground">
                                {formatRelativeTime(row.instance.lastSeenAt)}
                              </span>
                            </TooltipTrigger>
                            <TooltipContent>{formatAbsolute(row.instance.lastSeenAt, 'timestamp')}</TooltipContent>
                          </Tooltip>
                          {stale && (
                            <Badge
                              variant="outline"
                              className="bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-800 text-xs"
                            >
                              stale
                            </Badge>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-2">
                        {row.instance.revisionUpdatedAt ? (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span className="text-xs text-muted-foreground whitespace-nowrap">
                                {formatRelativeTime(row.instance.revisionUpdatedAt)}
                              </span>
                            </TooltipTrigger>
                            <TooltipContent>
                              {formatAbsolute(row.instance.revisionUpdatedAt, 'timestamp')}
                            </TooltipContent>
                          </Tooltip>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="px-4 py-2">
                        <span className="text-xs text-muted-foreground">{row.instance.trigger ?? '-'}</span>
                      </td>
                      <td className="px-4 py-2">
                        <code className="font-mono text-xs">{shortenRevision(row.instance.revision)}</code>
                      </td>
                      <td className="px-4 py-2">
                        <div className="flex flex-col gap-1">
                          <Badge
                            variant="outline"
                            className={`text-xs w-fit ${outcomeBadgeClass(INSTANCE_OUTCOME_KIND[row.instance.outcome])}`}
                          >
                            {row.instance.outcome}
                          </Badge>
                          {row.instance.error && (
                            <span className="text-[11px] text-red-600 dark:text-red-400 max-w-[16rem]">
                              {row.instance.error}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-2">
                        {row.instance.units.length === 0 ? (
                          <span className="text-xs text-muted-foreground">-</span>
                        ) : (
                          <ul className="flex flex-col gap-1">
                            {row.instance.units.map((unit) => (
                              <li key={unit.id} className="flex flex-col pl-2 border-l border-border">
                                <div className="flex items-center gap-1.5">
                                  <span className="text-xs">{unit.name}</span>
                                  <Badge
                                    variant="outline"
                                    className={`text-xs ${outcomeBadgeClass(UNIT_OUTCOME_KIND[unit.outcome])}`}
                                  >
                                    {unit.outcome}
                                  </Badge>
                                </div>
                                {unit.error && (
                                  <span className="text-[11px] text-red-600 dark:text-red-400">
                                    {unit.error}
                                  </span>
                                )}
                              </li>
                            ))}
                          </ul>
                        )}
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
