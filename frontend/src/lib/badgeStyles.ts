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

// Semantic outcome axis (success/error/warning/info/neutral), distinct from
// the config-identity axis above. These bg/text/border tuples were
// duplicated verbatim across ReloadStatusPage, AuditPage, ImportEnvDialog,
// TokensPage, and CreateTokenDialog before this consolidation -- pulled
// here as a single source of truth, not a new visual design (byte-identical
// to what each site had).
export type OutcomeKind = 'success' | 'error' | 'warning' | 'info' | 'neutral';

interface OutcomeClassSet {
  // bg + text + border (light + dark) -- a full `Badge` className.
  badge: string;
  // bg + border only (light + dark), no text color -- for `Alert` banners,
  // which apply their own (sometimes differently-shaded) text color.
  container: string;
  // text color only (light + dark) -- for description/detail text that
  // shares the badge's text shade.
  text: string;
}

const OUTCOME_CLASSES: Record<OutcomeKind, OutcomeClassSet> = {
  success: {
    badge: 'bg-green-50 text-green-700 border-green-200 dark:bg-green-950 dark:text-green-300 dark:border-green-800',
    container: 'bg-green-50 border-green-200 dark:bg-green-950 dark:border-green-800',
    text: 'text-green-700 dark:text-green-300'
  },
  error: {
    badge: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-950 dark:text-red-300 dark:border-red-800',
    container: 'bg-red-50 border-red-200 dark:bg-red-950 dark:border-red-800',
    text: 'text-red-700 dark:text-red-300'
  },
  warning: {
    badge: 'bg-yellow-50 text-yellow-700 border-yellow-200 dark:bg-yellow-950 dark:text-yellow-300 dark:border-yellow-800',
    container: 'bg-yellow-50 border-yellow-200 dark:bg-yellow-950 dark:border-yellow-800',
    text: 'text-yellow-700 dark:text-yellow-300'
  },
  info: {
    badge: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-300 dark:border-blue-800',
    container: 'bg-blue-50 border-blue-200 dark:bg-blue-950 dark:border-blue-800',
    text: 'text-blue-700 dark:text-blue-300'
  },
  neutral: {
    badge: 'bg-muted text-muted-foreground border-border',
    container: 'bg-muted border-border',
    text: 'text-muted-foreground'
  }
};

export function outcomeBadgeClass(outcome: OutcomeKind): string {
  return OUTCOME_CLASSES[outcome].badge;
}

export function outcomeAlertClass(outcome: OutcomeKind): string {
  return OUTCOME_CLASSES[outcome].container;
}

export function outcomeTextClass(outcome: OutcomeKind): string {
  return OUTCOME_CLASSES[outcome].text;
}
