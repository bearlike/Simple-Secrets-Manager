import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { XIcon, ScrollTextIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select';
import { getAuditEvents } from '../lib/api/audit';
import { getProjects } from '../lib/api/projects';
import { getConfigs } from '../lib/api/configs';
import { queryKeys } from '../lib/api/queryKeys';
import { EmptyState } from '../components/common/EmptyState';
import { outcomeBadgeClass } from '../lib/badgeStyles';

const AUDIT_PAGE_SIZE = 50;

function toSinceIso(date: string): string | undefined {
  if (!date) return undefined;
  return new Date(`${date}T00:00:00.000Z`).toISOString();
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toISOString().replace('T', ' ').slice(0, 19);
}

export function AuditPage() {
  // project/config live in the URL so /audit?project=&config= is a
  // deterministic, bookmarkable view ConfigUsageDialog can deep-link into;
  // since/page stay local, as ephemeral refinements of that scope.
  const [searchParams, setSearchParams] = useSearchParams();
  const projectFilter = searchParams.get('project') ?? '';
  const configFilter = searchParams.get('config') ?? '';
  const [sinceDate, setSinceDate] = useState('');
  const [page, setPage] = useState(1);

  // A config slug is only meaningful under its project, so setting the project
  // always clears the config; any scope change resets pagination.
  const applyScope = (project: string, config: string) => {
    const next: Record<string, string> = {};
    if (project) next.project = project;
    if (project && config) next.config = config;
    setSearchParams(next, { replace: true });
    setPage(1);
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

  const sinceIso = useMemo(() => toSinceIso(sinceDate), [sinceDate]);

  const { data, isLoading, isFetching } = useQuery({
    queryKey: queryKeys.audit({
      projectSlug: projectFilter || undefined,
      configSlug: configFilter || undefined,
      since: sinceIso,
      page,
      limit: AUDIT_PAGE_SIZE
    }),
    queryFn: () =>
      getAuditEvents({
        projectSlug: projectFilter || undefined,
        configSlug: configFilter || undefined,
        since: sinceIso,
        page,
        limit: AUDIT_PAGE_SIZE
      })
  });

  const events = data?.events ?? [];
  const hasNext = data?.hasNext ?? false;

  const hasFilters = Boolean(projectFilter || configFilter || sinceDate);

  const clearFilters = () => {
    setSinceDate('');
    applyScope('', '');
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-lg font-semibold">Audit Log</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Track all actions performed in your workspace
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2 mb-4">
        <Select
          value={projectFilter || 'all'}
          onValueChange={(value) => applyScope(value === 'all' ? '' : value, '')}
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
              applyScope(projectFilter, value === 'all' ? '' : value)
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

        <Input
          type="date"
          value={sinceDate}
          onChange={(event) => {
            setSinceDate(event.target.value);
            setPage(1);
          }}
          className="h-8 w-40 text-xs"
          placeholder="Since"
        />

        {hasFilters && (
          <Button variant="ghost" size="sm" className="h-8 gap-1.5 text-xs" onClick={clearFilters}>
            <XIcon className="h-3 w-3" />
            Clear
          </Button>
        )}
      </div>

      <div className="rounded-md border border-border">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[980px] text-sm">
            <thead>
              <tr className="bg-muted/40 border-b border-border">
                <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider text-muted-foreground">
                  TIMESTAMP
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider text-muted-foreground">
                  ACTOR
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider text-muted-foreground">
                  ACTION
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider text-muted-foreground">
                  PROJECT
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider text-muted-foreground">
                  CONFIG
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider text-muted-foreground">
                  KEY
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider text-muted-foreground">
                  STATUS
                </th>
              </tr>
            </thead>
            <tbody>
              {isLoading &&
                Array.from({ length: 8 }).map((_, rowIndex) => (
                  <tr key={rowIndex} className="border-b border-border last:border-0">
                    {Array.from({ length: 7 }).map((__, colIndex) => (
                      <td key={colIndex} className="px-4 py-2">
                        <Skeleton className="h-3.5 w-20" />
                      </td>
                    ))}
                  </tr>
                ))}

              {!isLoading &&
                events.length === 0 && (
                  <tr>
                    <td colSpan={7}>
                      <EmptyState
                        icon={ScrollTextIcon}
                        title="No audit events"
                        description={
                          hasFilters ? 'No events match your filters' : 'Actions will appear here as they happen'
                        }
                      />
                    </td>
                  </tr>
                )}

              {!isLoading &&
                events.map((event, rowIndex) => (
                  // Backend audit events carry no id, so mapAuditEventDto
                  // synthesizes one from their content — which collides for two
                  // same-millisecond keyless events (e.g. secrets.export). The
                  // row index disambiguates; the list is append-only and never
                  // reordered within a page, so it is a safe key here.
                  <tr
                    key={`${event.id}:${rowIndex}`}
                    className="border-b border-border last:border-0 hover:bg-muted/20 transition-colors"
                  >
                    <td className="px-4 py-2">
                      <span className="font-mono text-xs text-muted-foreground whitespace-nowrap">
                        {formatTimestamp(event.timestamp)}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-xs">{event.actor}</td>
                    <td className="px-4 py-2">
                      <code className="font-mono text-xs">{event.action}</code>
                    </td>
                    <td className="px-4 py-2">
                      <span className="font-mono text-xs text-muted-foreground">{event.projectSlug ?? '-'}</span>
                    </td>
                    <td className="px-4 py-2">
                      <span className="font-mono text-xs text-muted-foreground">{event.configSlug ?? '-'}</span>
                    </td>
                    <td className="px-4 py-2">
                      <span className="font-mono text-xs text-muted-foreground">{event.secretKey ?? '-'}</span>
                    </td>
                    <td className="px-4 py-2">
                      <Badge
                        variant="outline"
                        className={`${outcomeBadgeClass(event.status === 'success' ? 'success' : 'error')} text-xs`}
                      >
                        {event.status}
                      </Badge>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between">
        <p className="text-xs text-muted-foreground">
          Page {page}
          {isFetching && !isLoading ? ' | Refreshing...' : ''}
        </p>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 px-3 text-xs"
            onClick={() => setPage((current) => Math.max(1, current - 1))}
            disabled={isLoading || page <= 1}
          >
            Previous
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 px-3 text-xs"
            onClick={() => setPage((current) => current + 1)}
            disabled={isLoading || !hasNext}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
