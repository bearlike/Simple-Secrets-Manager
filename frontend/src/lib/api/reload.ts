import { apiClient } from './client';
import { mapReloadConfigStatusDto } from './mappers';
import { parseListSafely, reloadConfigStatusDtoSchema } from './schemas';
import type { ReloadConfigStatus, ReloadStatusResponseDto } from './types';

interface ReloadStatusFilters {
  projectSlug?: string;
  configSlug?: string;
}

export async function getReloadStatus(
  filters: ReloadStatusFilters = {}
): Promise<ReloadConfigStatus[]> {
  const params = new URLSearchParams();

  if (filters.projectSlug) params.set('project', filters.projectSlug);
  if (filters.configSlug) params.set('config', filters.configSlug);

  const query = params.toString();
  const response = await apiClient<ReloadStatusResponseDto>(
    `/reload/status${query ? `?${query}` : ''}`
  );
  return parseListSafely(reloadConfigStatusDtoSchema, response.data).map(mapReloadConfigStatusDto);
}
