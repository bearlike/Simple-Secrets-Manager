export const queryKeys = {
  me: () => ['me'] as const,
  onboardingStatus: () => ['onboarding', 'status'] as const,
  appVersion: () => ['app', 'version'] as const,
  projects: (archived?: boolean) =>
    (archived ? (['projects', 'archived'] as const) : (['projects'] as const)),
  project: (slug: string) => ['projects', slug] as const,
  configs: (projectSlug: string) => ['configs', projectSlug] as const,
  // Prefix-only key for project-wide invalidation (e.g. after an icon
  // recompute touches every config's secrets) -- matches (and invalidates)
  // every `secrets(projectSlug, *)`/`secretsView(projectSlug, *)` key below.
  secretsForProject: (projectSlug: string) => ['secrets', projectSlug] as const,
  secrets: (projectSlug: string, configSlug: string) =>
    ['secrets', projectSlug, configSlug] as const,
  secretsView: (projectSlug: string, configSlug: string, parentSlug?: string) =>
    ['secrets', projectSlug, configSlug, 'view', parentSlug ?? null] as const,
  iconifyCollections: () => ['iconify', 'collections'] as const,
  iconifyCollection: (prefix: string) => ['iconify', 'collection', prefix] as const,
  iconifySearch: (query: string, pack: string) => ['iconify', 'search', pack, query] as const,
  tokens: () => ['tokens'] as const,
  audit: (filters?: {
    projectSlug?: string;
    configSlug?: string;
    since?: string;
    page?: number;
    limit?: number;
  }) => ['audit', filters] as const,
  reloadStatus: (filters?: { projectSlug?: string; configSlug?: string }) =>
    ['reload-status', filters] as const,
  compareSecret: (
    projectSlug: string,
    key: string,
    options?: {
      includeParent?: boolean;
      includeMeta?: boolean;
      includeEmpty?: boolean;
      resolveReferences?: boolean;
      raw?: boolean;
      limitConfigs?: number;
    }
  ) => ['compare-secret', projectSlug, key, options] as const,
  // Prefix-only key for project-wide invalidation -- matches every
  // `compareSecret(projectSlug, *)` key above.
  compareSecretForProject: (projectSlug: string) => ['compare-secret', projectSlug] as const,
  referenceSuggestionKeys: (projectSlug: string, configSlug: string) =>
    ['reference-suggestions', 'keys', projectSlug, configSlug] as const,
  referenceSuggestionConfigs: (projectSlug: string) =>
    ['reference-suggestions', 'configs', projectSlug] as const,
  referenceSuggestionProjects: () => ['reference-suggestions', 'projects'] as const,
  workspaceSettings: () => ['workspace-settings'] as const,
  workspaceMembers: () => ['workspace-members'] as const,
  workspaceGroups: () => ['workspace-groups'] as const,
  workspaceGroupMembers: (groupSlug: string) => ['workspace-group-members', groupSlug] as const,
  workspaceMappings: () => ['workspace-mappings'] as const,
  workspaceProjectMembers: (projectSlug: string) => ['workspace-project-members', projectSlug] as const
};
