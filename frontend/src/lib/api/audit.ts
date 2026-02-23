import { apiClient } from './client';
import { mapAuditEventDto } from './mappers';
import type { AuditEvent, AuditEventsResponseDto } from './types';

interface AuditFilters {
  projectSlug?: string;
  configSlug?: string;
  since?: string;
  limit?: number;
}

export async function getAuditEvents(filters: AuditFilters = {}): Promise<AuditEvent[]> {
  const params = new URLSearchParams();

  if (filters.projectSlug) params.set('project', filters.projectSlug);
  if (filters.configSlug) params.set('config', filters.configSlug);
  if (filters.since) params.set('since', filters.since);
  params.set('limit', String(filters.limit ?? 100));

  const response = await apiClient<AuditEventsResponseDto>(`/audit/events?${params.toString()}`);
  return (response.events ?? []).map(mapAuditEventDto);
}
