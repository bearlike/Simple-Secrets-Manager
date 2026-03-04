import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PlusIcon, GitBranchIcon, ArrowRightIcon, RefreshCwIcon } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { getProjects } from '../lib/api/projects';
import { getConfigs } from '../lib/api/configs';
import { recomputeProjectSecretIcons } from '../lib/api/secrets';
import { queryKeys } from '../lib/api/queryKeys';
import { CreateConfigDialog } from '../components/configs/CreateConfigDialog';
import { EmptyState } from '../components/common/EmptyState';
import { notifyApiError } from '../lib/api/errorToast';

export function ConfigSettingsPage() {
  const { projectSlug = '' } = useParams<{ projectSlug: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);

  const { data: projects = [] } = useQuery({
    queryKey: queryKeys.projects(),
    queryFn: getProjects
  });

  const { data: configs = [], isLoading } = useQuery({
    queryKey: queryKeys.configs(projectSlug),
    queryFn: () => getConfigs(projectSlug),
    enabled: !!projectSlug
  });

  const currentProject = projects.find((project) => project.slug === projectSlug);
  const recomputeIconsMutation = useMutation({
    mutationFn: () => recomputeProjectSecretIcons(projectSlug),
    onSuccess: (summary) => {
      queryClient.invalidateQueries({ queryKey: ['secrets', projectSlug] });
      queryClient.invalidateQueries({ queryKey: ['compare-secret', projectSlug] });
      toast.success(
        `Auto icons refreshed: ${summary.keysUpdated}/${summary.keysScanned} keys updated (${summary.secretsUpdated} secrets)`
      );
    },
    onError: (error) => {
      notifyApiError(error, 'Failed to refresh auto icons');
    }
  });

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-lg font-semibold">{currentProject?.name ?? projectSlug} - Settings</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Manage environments and configurations</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            className="gap-1.5"
            onClick={() => recomputeIconsMutation.mutate()}
            disabled={!projectSlug || recomputeIconsMutation.isPending}
          >
            <RefreshCwIcon className={`h-3.5 w-3.5 ${recomputeIconsMutation.isPending ? 'animate-spin' : ''}`} />
            Refresh Auto Icons
          </Button>
          <Button size="sm" className="gap-1.5" onClick={() => setCreateOpen(true)}>
            <PlusIcon className="h-3.5 w-3.5" />
            New Config
          </Button>
        </div>
      </div>

      <div className="rounded-md border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-muted/40 border-b border-border">
              <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider text-muted-foreground">
                NAME
              </th>
              <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider text-muted-foreground">
                SLUG
              </th>
              <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider text-muted-foreground">
                PARENT
              </th>
              <th className="px-4 py-2.5 text-left text-xs font-medium tracking-wider text-muted-foreground">
                CREATED
              </th>
              <th className="px-4 py-2.5 text-right text-xs font-medium tracking-wider text-muted-foreground">
                ACTION
              </th>
            </tr>
          </thead>
          <tbody>
            {isLoading &&
              Array.from({ length: 3 }).map((_, index) => (
                <tr key={index} className="border-b border-border last:border-0">
                  {Array.from({ length: 5 }).map((__, colIndex) => (
                    <td key={colIndex} className="px-4 py-2.5">
                      <Skeleton className="h-4 w-20" />
                    </td>
                  ))}
                </tr>
              ))}

            {!isLoading &&
              configs.length === 0 && (
                <tr>
                  <td colSpan={5}>
                    <EmptyState
                      icon={GitBranchIcon}
                      title="No configs yet"
                      description="Create your first environment config"
                      action={
                        <Button size="sm" onClick={() => setCreateOpen(true)}>
                          <PlusIcon className="h-3.5 w-3.5 mr-1.5" />
                          New Config
                        </Button>
                      }
                    />
                  </td>
                </tr>
              )}

            {!isLoading &&
              configs.map((config) => (
                <tr
                  key={config.slug}
                  className="border-b border-border last:border-0 hover:bg-muted/20 transition-colors cursor-pointer"
                  onClick={() => navigate(`/projects/${projectSlug}/configs/${config.slug}`)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      navigate(`/projects/${projectSlug}/configs/${config.slug}`);
                    }
                  }}
                  tabIndex={0}
                  role="button"
                >
                  <td className="px-4 py-2.5 font-medium text-sm">{config.name}</td>
                  <td className="px-4 py-2.5">
                    <code className="font-mono text-xs text-muted-foreground">{config.slug}</code>
                  </td>
                  <td className="px-4 py-2.5">
                    {config.parentSlug ? (
                      <div className="flex items-center gap-1.5">
                        <GitBranchIcon className="h-3 w-3 text-muted-foreground" />
                        <Badge variant="outline" className="text-xs font-mono">
                          {config.parentSlug}
                        </Badge>
                      </div>
                    ) : (
                      <span className="text-xs text-muted-foreground">-</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-muted-foreground">
                    {config.createdAt ? new Date(config.createdAt).toLocaleDateString() : '-'}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 gap-1.5 text-xs"
                      onClick={(event) => {
                        event.stopPropagation();
                        navigate(`/projects/${projectSlug}/configs/${config.slug}`);
                      }}
                      aria-label={`Open ${config.slug}`}
                    >
                      Open
                      <ArrowRightIcon className="h-3.5 w-3.5" />
                    </Button>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-muted-foreground mt-3">
        Config deletion is not available in the current backend API.
      </p>

      <CreateConfigDialog
        projectSlug={projectSlug}
        open={createOpen}
        onOpenChange={setCreateOpen}
        existingConfigs={configs}
      />
    </div>
  );
}
