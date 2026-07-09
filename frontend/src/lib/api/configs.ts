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

interface UpdateConfigInput {
  name?: string;
  // undefined: leave the parent unchanged; null or '': clear it;
  // a slug: set that config as the parent.
  parentSlug?: string | null;
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

export async function updateConfig(
  projectSlug: string,
  configSlug: string,
  data: UpdateConfigInput
): Promise<Config> {
  const body: Record<string, string> = {};
  if (data.name !== undefined) {
    body.name = data.name;
  }
  if (data.parentSlug !== undefined) {
    body.parent = data.parentSlug ?? '';
  }

  const response = await apiClient<CreateConfigResponseDto>(
    `/projects/${projectSlug}/configs/${configSlug}`,
    {
      method: 'PATCH',
      body: JSON.stringify(body)
    }
  );

  return mapConfigDto(response.config);
}

export async function deleteConfig(
  projectSlug: string,
  configSlug: string
): Promise<void> {
  await apiClient<{ status?: string }>(
    `/projects/${projectSlug}/configs/${configSlug}`,
    { method: 'DELETE' }
  );
}
