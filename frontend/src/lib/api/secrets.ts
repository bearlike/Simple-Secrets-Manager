import { apiClient, apiClientText } from './client';
import { mapSecretsData } from './mappers';
import type {
  BulkExportResult,
  Secret,
  SecretsJsonResponseDto
} from './types';

interface SecretValueInput {
  value: string;
}

interface SecretUpsertInput {
  key: string;
  value: string;
}

function secretsEndpoint(
  projectSlug: string,
  configSlug: string,
  params: Record<string, string | boolean>
): string {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    searchParams.set(key, String(value));
  });

  return `/projects/${projectSlug}/configs/${configSlug}/secrets?${searchParams.toString()}`;
}

export async function getSecrets(projectSlug: string, configSlug: string): Promise<Secret[]> {
  const response = await apiClient<SecretsJsonResponseDto>(
    secretsEndpoint(projectSlug, configSlug, {
      format: 'json',
      include_parent: true
    })
  );

  return mapSecretsData(response.data ?? {});
}

export async function createSecret(
  projectSlug: string,
  configSlug: string,
  data: SecretUpsertInput
): Promise<Secret> {
  await apiClient<void>(
    `/projects/${projectSlug}/configs/${configSlug}/secrets/${encodeURIComponent(data.key)}`,
    {
      method: 'PUT',
      body: JSON.stringify({ value: data.value })
    }
  );

  return {
    key: data.key,
    value: data.value,
    updatedAt: undefined
  };
}

export async function updateSecret(
  projectSlug: string,
  configSlug: string,
  key: string,
  data: SecretValueInput
): Promise<Secret> {
  await apiClient<void>(
    `/projects/${projectSlug}/configs/${configSlug}/secrets/${encodeURIComponent(key)}`,
    {
      method: 'PUT',
      body: JSON.stringify({ value: data.value })
    }
  );

  return {
    key,
    value: data.value,
    updatedAt: undefined
  };
}

export function deleteSecret(projectSlug: string, configSlug: string, key: string) {
  return apiClient<void>(
    `/projects/${projectSlug}/configs/${configSlug}/secrets/${encodeURIComponent(key)}`,
    {
      method: 'DELETE'
    }
  );
}

export async function bulkExport(
  projectSlug: string,
  configSlug: string,
  format: 'json' | 'env'
): Promise<BulkExportResult> {
  const endpoint = secretsEndpoint(projectSlug, configSlug, {
    format,
    include_parent: true
  });

  if (format === 'env') {
    const text = await apiClientText(endpoint);
    return {
      format: 'env',
      data: text
    };
  }

  const response = await apiClient<SecretsJsonResponseDto>(endpoint);
  return {
    format: 'json',
    data: response.data ?? {}
  };
}
