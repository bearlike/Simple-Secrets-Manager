import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangleIcon, EyeIcon, EyeOffIcon, GitCompareArrowsIcon, SearchIcon } from 'lucide-react';
import { useParams, useSearchParams } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/common/EmptyState';
import { getSecretComparison } from '../lib/api/compare';
import { getProjects } from '../lib/api/projects';
import { queryKeys } from '../lib/api/queryKeys';

const ISSUE_MISSING_EFFECTIVE_VALUE = 'missing_effective_value';
const BROKEN_REFERENCE_PREFIX = 'broken_reference_';

type CompareIssueFilter = 'all' | 'only_issues' | 'missing' | 'broken_refs';

function formatUpdatedAt(value?: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toISOString().replace('T', ' ').slice(0, 19);
}

function issueBadgeLabel(code: string): string {
  if (code === ISSUE_MISSING_EFFECTIVE_VALUE) return 'Missing value';
  if (code === 'broken_reference_unresolved') return 'Unresolved reference';
  if (code === 'broken_reference_syntax') return 'Invalid reference syntax';
  if (code === 'broken_reference_cycle_or_depth') return 'Reference cycle/depth';
  return code.replace(/_/g, ' ');
}

export function CompareBySecretPage() {
  const { projectSlug = '' } = useParams<{ projectSlug: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const keyFromUrl = (searchParams.get('key') ?? '').trim();

  const [keyInput, setKeyInput] = useState(keyFromUrl);
  const [targetKey, setTargetKey] = useState(keyFromUrl);
  const [resolvedMode, setResolvedMode] = useState(true);
  const [includeEmpty, setIncludeEmpty] = useState(true);
  const [revealAll, setRevealAll] = useState(false);
  const [issueFilter, setIssueFilter] = useState<CompareIssueFilter>('all');
  const [revealedConfigSlugs, setRevealedConfigSlugs] = useState<Set<string>>(new Set());

  useEffect(() => {
    setKeyInput(keyFromUrl);
    setTargetKey(keyFromUrl);
    setRevealAll(false);
    setRevealedConfigSlugs(new Set());
  }, [keyFromUrl]);

  const { data: projects = [] } = useQuery({
    queryKey: queryKeys.projects(),
    queryFn: getProjects
  });
  const currentProject = projects.find((project) => project.slug === projectSlug);

  const comparisonQuery = useQuery({
    queryKey: queryKeys.compareSecret(projectSlug, targetKey, {
      includeEmpty,
      resolveReferences: resolvedMode,
      raw: !resolvedMode
    }),
    queryFn: () =>
      getSecretComparison(projectSlug, targetKey, {
        includeEmpty,
        resolveReferences: resolvedMode,
        raw: !resolvedMode
      }),
    enabled: !!projectSlug && !!targetKey
  });

  const rows = useMemo(() => comparisonQuery.data?.configs ?? [], [comparisonQuery.data?.configs]);
  const filteredRows = useMemo(() => {
    return rows.filter((row) => {
      const issues = row.issues ?? [];
      if (issueFilter === 'only_issues') return issues.length > 0;
      if (issueFilter === 'missing') {
        return issues.some((issue) => issue.code === ISSUE_MISSING_EFFECTIVE_VALUE);
      }
      if (issueFilter === 'broken_refs') {
        return issues.some((issue) => issue.code.startsWith(BROKEN_REFERENCE_PREFIX));
      }
      return true;
    });
  }, [issueFilter, rows]);

  const submitKey = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = keyInput.trim();
    if (!trimmed) return;
    setTargetKey(trimmed);
    setSearchParams({ key: trimmed });
  };

  const toggleRevealRow = (configSlug: string) => {
    setRevealedConfigSlugs((prev) => {
      const next = new Set(prev);
      if (next.has(configSlug)) {
        next.delete(configSlug);
      } else {
        next.add(configSlug);
      }
      return next;
    });
  };

  const errorMessage = comparisonQuery.error instanceof Error ? comparisonQuery.error.message : 'Failed to compare';
  const issueSummary = comparisonQuery.data?.issuesSummary;
  const issueCountByCode = useMemo(() => {
    const map = new Map<string, number>();
    for (const entry of issueSummary?.byCode ?? []) {
      map.set(entry.code, entry.count);
    }
    return map;
  }, [issueSummary?.byCode]);
  const missingIssueCount = issueCountByCode.get(ISSUE_MISSING_EFFECTIVE_VALUE) ?? 0;
  const brokenReferenceIssueCount = Array.from(issueCountByCode.entries()).reduce((acc, [code, count]) => {
    if (code.startsWith(BROKEN_REFERENCE_PREFIX)) return acc + count;
    return acc;
  }, 0);
  const noResults = comparisonQuery.isSuccess && filteredRows.length === 0;

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-4">
      <div>
        <h1 className="text-lg font-semibold">Compare By Secret</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Compare one secret key across configs in {currentProject?.name ?? projectSlug}
        </p>
      </div>

      <form onSubmit={submitKey} className="flex flex-wrap items-center gap-2">
        <div className="relative w-full max-w-sm">
          <SearchIcon className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={keyInput}
            onChange={(event) => setKeyInput(event.target.value)}
            placeholder="Enter secret key (e.g. DATABASE_URL)"
            className="pl-8 h-9 text-sm font-mono"
          />
        </div>
        <Button type="submit" size="sm" className="h-9">
          Compare
        </Button>
        <Button
          type="button"
          variant={resolvedMode ? 'default' : 'outline'}
          size="sm"
          className="h-9"
          onClick={() => setResolvedMode(true)}
        >
          Resolved
        </Button>
        <Button
          type="button"
          variant={!resolvedMode ? 'default' : 'outline'}
          size="sm"
          className="h-9"
          onClick={() => setResolvedMode(false)}
        >
          Raw
        </Button>
        <Button
          type="button"
          variant={includeEmpty ? 'default' : 'outline'}
          size="sm"
          className="h-9"
          onClick={() => setIncludeEmpty((current) => !current)}
        >
          {includeEmpty ? 'Including Missing' : 'Hide Missing'}
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-9"
          onClick={() => setRevealAll((current) => !current)}
        >
          {revealAll ? 'Mask All' : 'Reveal All'}
        </Button>
        <Button
          type="button"
          variant={issueFilter === 'all' ? 'default' : 'outline'}
          size="sm"
          className="h-9"
          onClick={() => setIssueFilter('all')}
        >
          All
        </Button>
        <Button
          type="button"
          variant={issueFilter === 'only_issues' ? 'default' : 'outline'}
          size="sm"
          className="h-9"
          onClick={() => setIssueFilter('only_issues')}
        >
          Only Issues
        </Button>
        <Button
          type="button"
          variant={issueFilter === 'missing' ? 'default' : 'outline'}
          size="sm"
          className="h-9"
          onClick={() => setIssueFilter('missing')}
        >
          Missing
        </Button>
        <Button
          type="button"
          variant={issueFilter === 'broken_refs' ? 'default' : 'outline'}
          size="sm"
          className="h-9"
          onClick={() => setIssueFilter('broken_refs')}
        >
          Broken refs
        </Button>
      </form>

      {!!issueSummary && (
        <div className="flex items-center gap-2">
          {issueSummary.totalIssues > 0 ?
          <>
              {missingIssueCount > 0 && (
                <Badge variant="outline" className="text-xs border-amber-500 text-amber-700">
                  {missingIssueCount} missing
                </Badge>
              )}
              {brokenReferenceIssueCount > 0 && (
                <Badge variant="outline" className="text-xs border-red-500 text-red-700">
                  {brokenReferenceIssueCount} broken refs
                </Badge>
              )}
              <Badge variant="outline" className="text-xs">
                {issueSummary.affectedConfigs} configs affected
              </Badge>
            </> :
          <Badge variant="outline" className="text-xs border-emerald-500 text-emerald-700">
              No issues detected
            </Badge>
          }
        </div>
      )}

      {comparisonQuery.isError && (
        <div className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          {errorMessage}
        </div>
      )}

      {!targetKey && (
        <EmptyState
          icon={GitCompareArrowsIcon}
          title="Choose a secret key"
          description="Enter a key to compare how its value differs across configs."
        />
      )}

      {targetKey && (
        <div className="rounded-md border border-border">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-sm">
              <thead>
                <tr className="bg-muted/40 border-b border-border">
                  <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider text-muted-foreground">
                    CONFIG
                  </th>
                  <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider text-muted-foreground">
                    VALUE
                  </th>
                  <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider text-muted-foreground">
                    SOURCE
                  </th>
                  <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider text-muted-foreground">
                    UPDATED
                  </th>
                  <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider text-muted-foreground">
                    ISSUES
                  </th>
                  <th className="px-4 py-2.5 text-right text-xs font-medium tracking-wider text-muted-foreground">
                    ACTION
                  </th>
                </tr>
              </thead>
              <tbody>
                {comparisonQuery.isLoading &&
                  Array.from({ length: 6 }).map((_, rowIndex) => (
                    <tr key={rowIndex} className="border-b border-border last:border-0">
                      {Array.from({ length: 6 }).map((__, colIndex) => (
                        <td key={colIndex} className="px-4 py-2">
                          <Skeleton className="h-3.5 w-24" />
                        </td>
                      ))}
                    </tr>
                  ))}

                {noResults && (
                  <tr>
                    <td colSpan={6}>
                      <EmptyState
                        icon={GitCompareArrowsIcon}
                        title="No matching rows"
                        description={
                          rows.length === 0
                            ? 'This key has no visible values in this project.'
                            : 'No rows match the current issue filter.'
                        }
                      />
                    </td>
                  </tr>
                )}

                {!comparisonQuery.isLoading &&
                  filteredRows.map((row) => {
                    const visible = revealAll || revealedConfigSlugs.has(row.configSlug);
                    const value = row.effective.value;
                    const hasValue = value !== null;
                    const issues = row.issues ?? [];
                    const hasIssues = issues.length > 0;
                    const source = row.effective.isInherited ? `inherited from ${row.effective.source}` : 'direct';
                    return (
                      <tr
                        key={row.configSlug}
                        className={`border-b border-border last:border-0 ${
                          hasIssues ? 'bg-amber-50/30 dark:bg-amber-950/20' : 'hover:bg-muted/20'
                        }`}
                      >
                        <td className="px-4 py-2">
                          <div className="flex items-center gap-2">
                            <code className="font-mono text-xs">{row.configSlug}</code>
                            {hasIssues && <AlertTriangleIcon className="h-3.5 w-3.5 text-amber-600" />}
                          </div>
                        </td>
                        <td className="px-4 py-2">
                          {hasValue ?
                          visible ?
                          <code className="font-mono text-xs break-all">{value}</code> :
                          <span className="font-mono text-xs text-muted-foreground">••••••••••••</span> :
                          <span className="text-xs text-muted-foreground">Missing</span>}
                        </td>
                        <td className="px-4 py-2">
                          <span className="text-xs text-muted-foreground">{hasValue ? source : '—'}</span>
                        </td>
                        <td className="px-4 py-2">
                          <span className="font-mono text-xs text-muted-foreground">
                            {formatUpdatedAt(row.meta?.updatedAt)}
                          </span>
                        </td>
                        <td className="px-4 py-2">
                          {hasIssues ?
                          <div className="flex flex-wrap items-center gap-1">
                              {issues.map((issue) => (
                                <Badge
                                  key={`${row.configSlug}-${issue.code}`}
                                  variant="outline"
                                  className={`text-[10px] ${
                                    issue.code === ISSUE_MISSING_EFFECTIVE_VALUE ?
                                      'border-amber-500 text-amber-700' :
                                      'border-red-500 text-red-700'
                                  }`}
                                  title={issue.message}
                                >
                                  {issueBadgeLabel(issue.code)}
                                </Badge>
                              ))}
                            </div> :
                          <span className="text-xs text-muted-foreground">—</span>}
                        </td>
                        <td className="px-4 py-2">
                          <div className="flex items-center justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 w-7 p-0"
                              onClick={() => toggleRevealRow(row.configSlug)}
                              disabled={!hasValue}
                              aria-label={visible ? 'Hide value' : 'Reveal value'}
                            >
                              {visible ? <EyeOffIcon className="h-3.5 w-3.5" /> : <EyeIcon className="h-3.5 w-3.5" />}
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
