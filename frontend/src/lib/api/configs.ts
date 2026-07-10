import { apiClient } from './client';
import { mapConfigDto } from './mappers';
import { configDtoSchema, parseListSafely } from './schemas';
import type {
  Config,
  ConfigsResponseDto,
  CreateConfigResponseDto
} from './types';

interface CreateConfigInput {
  name: string;
  slug: string;
  parentSlug?: string;
  description?: string;
}

interface UpdateConfigInput {
  name?: string;
  // undefined: leave the parent unchanged; null or '': clear it;
  // a slug: set that config as the parent.
  parentSlug?: string | null;
  // undefined: leave the description unchanged; '' clears it.
  description?: string;
}

export async function getConfigs(projectSlug: string): Promise<Config[]> {
  const response = await apiClient<ConfigsResponseDto>(`/projects/${projectSlug}/configs`);
  return parseListSafely(configDtoSchema, response.configs).map(mapConfigDto);
}

export async function createConfig(projectSlug: string, data: CreateConfigInput): Promise<Config> {
  const response = await apiClient<CreateConfigResponseDto>(`/projects/${projectSlug}/configs`, {
    method: 'POST',
    body: JSON.stringify({
      name: data.name,
      slug: data.slug,
      parent: data.parentSlug,
      description: data.description
    })
  });

  return mapConfigDto(configDtoSchema.parse(response.config));
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
  if (data.description !== undefined) {
    body.description = data.description;
  }

  const response = await apiClient<CreateConfigResponseDto>(
    `/projects/${projectSlug}/configs/${configSlug}`,
    {
      method: 'PATCH',
      body: JSON.stringify(body)
    }
  );

  return mapConfigDto(configDtoSchema.parse(response.config));
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
