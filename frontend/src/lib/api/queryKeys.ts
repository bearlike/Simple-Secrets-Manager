export const queryKeys = {
  me: () => ['me'] as const,
  onboardingStatus: () => ['onboarding', 'status'] as const,
  appVersion: () => ['app', 'version'] as const,
  projects: () => ['projects'] as const,
  project: (slug: string) => ['projects', slug] as const,
  configs: (projectSlug: string) => ['configs', projectSlug] as const,
  secrets: (projectSlug: string, configSlug: string) =>
    ['secrets', projectSlug, configSlug] as const,
  tokens: () => ['tokens'] as const,
  audit: (filters?: {
    projectSlug?: string;
    configSlug?: string;
    since?: string;
    page?: number;
    limit?: number;
  }) => ['audit', filters] as const,
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
  workspaceSettings: () => ['workspace-settings'] as const,
  workspaceMembers: () => ['workspace-members'] as const,
  workspaceGroups: () => ['workspace-groups'] as const,
  workspaceGroupMembers: (groupSlug: string) => ['workspace-group-members', groupSlug] as const,
  workspaceMappings: () => ['workspace-mappings'] as const,
  workspaceProjectMembers: (projectSlug: string) => ['workspace-project-members', projectSlug] as const
};
