import { apiClient } from './client';
import { mapAuditEventDto } from './mappers';
import type { AuditEventsPage, AuditEventsResponseDto } from './types';

interface AuditFilters {
  projectSlug?: string;
  configSlug?: string;
  since?: string;
  page?: number;
  limit?: number;
}

export async function getAuditEvents(filters: AuditFilters = {}): Promise<AuditEventsPage> {
  const params = new URLSearchParams();

  if (filters.projectSlug) params.set('project', filters.projectSlug);
  if (filters.configSlug) params.set('config', filters.configSlug);
  if (filters.since) params.set('since', filters.since);
  params.set('page', String(filters.page ?? 1));
  params.set('limit', String(filters.limit ?? 50));

  const response = await apiClient<AuditEventsResponseDto>(`/audit/events?${params.toString()}`);
  return {
    events: (response.events ?? []).map(mapAuditEventDto),
    page: response.page ?? filters.page ?? 1,
    limit: response.limit ?? filters.limit ?? 50,
    hasNext: Boolean(response.hasNext ?? response.has_next)
  };
}
