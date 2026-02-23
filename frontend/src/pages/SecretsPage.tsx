import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Badge } from '@/components/ui/badge';
import { SecretsTable } from '../components/secrets/SecretsTable';
import { getProjects } from '../lib/api/projects';
import { queryKeys } from '../lib/api/queryKeys';
function getConfigBadgeClass(configSlug: string): string {
  if (configSlug === 'dev' || configSlug === 'development')
  return 'bg-green-50 text-green-700 border-green-200';
  if (configSlug === 'staging')
  return 'bg-yellow-50 text-yellow-700 border-yellow-200';
  if (configSlug === 'prod' || configSlug === 'production')
  return 'bg-red-50 text-red-700 border-red-200';
  return '';
}
export function SecretsPage() {
  const { projectSlug = '', configSlug = '' } = useParams<{
    projectSlug: string;
    configSlug: string;
  }>();
  const { data: projects = [] } = useQuery({
    queryKey: queryKeys.projects(),
    queryFn: getProjects
  });
  const currentProject = projects.find((p) => p.slug === projectSlug);
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