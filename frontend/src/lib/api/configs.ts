import { apiClient } from './client';
import { mapConfigDto } from './mappers';
import type {
  Config,
  ConfigsResponseDto,
  CreateConfigResponseDto
} from './types';

interface CreateConfigInput {
  name: string;
  slug: string;
  parentSlug?: string;
}

export async function getConfigs(projectSlug: string): Promise<Config[]> {
  const response = await apiClient<ConfigsResponseDto>(`/projects/${projectSlug}/configs`);
  return (response.configs ?? []).map(mapConfigDto);
}

export async function createConfig(projectSlug: string, data: CreateConfigInput): Promise<Config> {
  const response = await apiClient<CreateConfigResponseDto>(`/projects/${projectSlug}/configs`, {
    method: 'POST',
    body: JSON.stringify({
      name: data.name,
      slug: data.slug,
      parent: data.parentSlug
    })
  });

  return mapConfigDto(response.config);
}
