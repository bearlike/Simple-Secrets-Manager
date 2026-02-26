export const queryKeys = {
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
    limit?: number;
  }) => ['audit', filters] as const
};
