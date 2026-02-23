import { GitBranchIcon } from 'lucide-react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { SecretsTable } from '../components/secrets/SecretsTable';
import { EmptyState } from '../components/common/EmptyState';
import { getConfigs } from '../lib/api/configs';
import { getProjects } from '../lib/api/projects';
import { queryKeys } from '../lib/api/queryKeys';
import { getConfigBadgeClass } from '../lib/badgeStyles';
export function SecretsPage() {
  const navigate = useNavigate();
  const { projectSlug = '', configSlug = '' } = useParams<{
    projectSlug: string;
    configSlug: string;
  }>();
  const { data: projects = [] } = useQuery({
    queryKey: queryKeys.projects(),
    queryFn: getProjects
  });
  const configsQuery = useQuery({
    queryKey: queryKeys.configs(projectSlug),
    queryFn: () => getConfigs(projectSlug),
    enabled: !!projectSlug
  });
  const currentProject = projects.find((p) => p.slug === projectSlug);
  const configs = configsQuery.data ?? [];
  const hasConfig = configs.some((config) => config.slug === configSlug);
  const missingConfig = configsQuery.isSuccess && !hasConfig;

  if (configsQuery.isLoading) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <p className="text-sm text-muted-foreground">Loading project config...</p>
      </div>
    );
  }

  if (missingConfig) {
    const noConfigsYet = configs.length === 0;
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <EmptyState
          icon={GitBranchIcon}
          title={noConfigsYet ? 'No configs yet' : 'Config not found'}
          description={
            noConfigsYet ?
            'Create a config for this project before adding secrets.' :
            `The config "${configSlug}" does not exist for this project.`
          }
          action={
            <Button size="sm" onClick={() => navigate(`/projects/${projectSlug}/settings`)}>
              Manage Configs
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h1 className="text-lg font-semibold">
              {currentProject?.name ?? projectSlug}
            </h1>
            <Badge
              variant="outline"
              className={`text-xs font-mono ${getConfigBadgeClass(configSlug)}`}>

              {configSlug}
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-0.5">
            Manage secrets for this environment
          </p>
        </div>
      </div>

      <SecretsTable projectSlug={projectSlug} configSlug={configSlug} />
    </div>);

}
