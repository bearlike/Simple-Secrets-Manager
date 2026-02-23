export function getConfigBadgeClass(configSlug: string): string {
  const normalizedSlug = configSlug.toLowerCase();

  if (normalizedSlug === 'dev' || normalizedSlug === 'development') {
    return 'bg-green-50 text-green-700 border-green-200 dark:bg-green-950 dark:text-green-300 dark:border-green-800';
  }

  if (normalizedSlug === 'staging') {
    return 'bg-yellow-50 text-yellow-700 border-yellow-200 dark:bg-yellow-950 dark:text-yellow-300 dark:border-yellow-800';
  }

  if (normalizedSlug === 'prod' || normalizedSlug === 'production') {
    return 'bg-red-50 text-red-700 border-red-200 dark:bg-red-950 dark:text-red-300 dark:border-red-800';
  }

  return 'bg-secondary text-secondary-foreground border-border';
}
