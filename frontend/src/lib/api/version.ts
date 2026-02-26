import { apiClient } from './client';

interface VersionResponseDto {
  status?: string;
  version?: string;
}

export async function getAppVersion(): Promise<string> {
  const response = await apiClient<VersionResponseDto>('/version');
  return typeof response.version === 'string' && response.version.trim()
    ? response.version.trim()
    : 'unknown';
}
