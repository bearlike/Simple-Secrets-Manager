import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getConfigs } from '../../lib/api/configs';
import { getProjects } from '../../lib/api/projects';
import { getSecretsKeyMap } from '../../lib/api/secrets';

interface UseReferenceSuggestionsInput {
  projectSlug: string;
  configSlug: string;
}

export function useReferenceSuggestions({ projectSlug, configSlug }: UseReferenceSuggestionsInput): string[] {
  const { data: keyMap = {} } = useQuery({
    queryKey: ['reference-suggestions', 'keys', projectSlug, configSlug],
    queryFn: () =>
      getSecretsKeyMap(projectSlug, configSlug, true, {
        raw: true,
        resolveReferences: false
      }),
    enabled: !!projectSlug && !!configSlug,
    staleTime: 60 * 1000
  });

  const { data: configs = [] } = useQuery({
    queryKey: ['reference-suggestions', 'configs', projectSlug],
    queryFn: () => getConfigs(projectSlug),
    enabled: !!projectSlug,
    staleTime: 60 * 1000
  });

  const { data: projects = [] } = useQuery({
    queryKey: ['reference-suggestions', 'projects'],
    queryFn: getProjects,
    staleTime: 60 * 1000
  });

  return useMemo(() => {
    const keys = Object.keys(keyMap).sort();
    const values = new Set<string>();

    keys.forEach((key) => values.add(key));
    configs.forEach((config) => {
      keys.forEach((key) => values.add(`${config.slug}.${key}`));
    });
    projects.forEach((project) => {
      keys.forEach((key) => values.add(`${project.slug}.${configSlug}.${key}`));
    });

    values.add('KEY');
    values.add('config.KEY');
    values.add('project.config.KEY');

    return Array.from(values).slice(0, 300);
  }, [keyMap, configs, projects, configSlug]);
}
