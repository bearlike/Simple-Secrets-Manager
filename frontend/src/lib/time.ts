// Shared relative/absolute time formatting -- previously duplicated (twice
// as a manual minutes/hours/days cascade, once as this Intl-based version)
// across SecretsTable, TokensTable, and ReloadStatusPage. See
// `frontend/AGENTS.md` session lessons for the consolidation rationale.

const EMPTY_PLACEHOLDER = '—';

function parseDate(value?: string | null): Date | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

/**
 * Human-readable relative time ("5 minutes ago", "in 2 hours"), backed by
 * `Intl.RelativeTimeFormat` so pluralization/phrasing is locale-correct
 * instead of a hand-rolled `${n}m ago` cascade. Missing/invalid input
 * degrades to the placeholder rather than throwing.
 */
export function formatRelativeTime(value?: string | null): string {
  const date = parseDate(value);
  if (!date) return EMPTY_PLACEHOLDER;

  const diffSeconds = Math.round((date.getTime() - Date.now()) / 1000);
  const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });

  const absSeconds = Math.abs(diffSeconds);
  if (absSeconds < 60) return rtf.format(diffSeconds, 'second');

  const diffMinutes = Math.round(diffSeconds / 60);
  if (Math.abs(diffMinutes) < 60) return rtf.format(diffMinutes, 'minute');

  const diffHours = Math.round(diffMinutes / 60);
  if (Math.abs(diffHours) < 24) return rtf.format(diffHours, 'hour');

  const diffDays = Math.round(diffHours / 24);
  return rtf.format(diffDays, 'day');
}

export type AbsoluteTimeStyle = 'datetime' | 'date' | 'timestamp';

/**
 * Absolute time for display. `'datetime'` (default) is a locale-formatted
 * date+time for general use; `'date'` is locale-formatted date-only (e.g.
 * token expiry); `'timestamp'` is a fixed UTC `YYYY-MM-DD HH:MM:SS` stamp
 * for operational contexts (the reloader fleet view) where a stable,
 * timezone-explicit format matters more than locale formatting.
 */
export function formatAbsolute(value?: string | null, style: AbsoluteTimeStyle = 'datetime'): string {
  const date = parseDate(value);
  if (!date) return EMPTY_PLACEHOLDER;

  if (style === 'date') return date.toLocaleDateString();
  if (style === 'timestamp') return date.toISOString().replace('T', ' ').slice(0, 19);
  return date.toLocaleString();
}
