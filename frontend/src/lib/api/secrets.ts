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

export interface SecretUpsertInput {
  key: string;
  value: string;
}

export interface SecretExportOptions {
  includeParent?: boolean;
  includeMeta?: boolean;
  resolveReferences?: boolean;
  raw?: boolean;
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

export async function getSecrets(
  projectSlug: string,
  configSlug: string,
  options?: SecretExportOptions
): Promise<Secret[]> {
  return mapSecretsData(await getSecretsKeyMap(projectSlug, configSlug, true, options));
}

export async function getSecretsKeyMap(
  projectSlug: string,
  configSlug: string,
  includeParent = true,
  options?: SecretExportOptions
): Promise<Record<string, string>> {
  const response = await apiClient<SecretsJsonResponseDto>(
    secretsEndpoint(projectSlug, configSlug, {
      format: 'json',
      include_parent: options?.includeParent ?? includeParent,
      include_meta: options?.includeMeta ?? false,
      resolve_references: options?.resolveReferences ?? false,
      raw: options?.raw ?? false
    })
  );

  return response.data ?? {};
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

export async function upsertSecretsBulk(
  projectSlug: string,
  configSlug: string,
  entries: SecretUpsertInput[]
): Promise<{ succeeded: number; failedKeys: string[] }> {
  const results = await Promise.allSettled(
    entries.map((entry) =>
      apiClient<void>(`/projects/${projectSlug}/configs/${configSlug}/secrets/${encodeURIComponent(entry.key)}`, {
        method: 'PUT',
        body: JSON.stringify({ value: entry.value })
      })
    )
  );

  const failedKeys: string[] = [];
  let succeeded = 0;
  results.forEach((result, index) => {
    if (result.status === 'fulfilled') {
      succeeded += 1;
      return;
    }
    failedKeys.push(entries[index].key);
  });

  return { succeeded, failedKeys };
}

export async function bulkExport(
  projectSlug: string,
  configSlug: string,
  format: 'json' | 'env',
  options?: SecretExportOptions
): Promise<BulkExportResult> {
  const endpoint = secretsEndpoint(projectSlug, configSlug, {
    format,
    include_parent: options?.includeParent ?? true,
    include_meta: options?.includeMeta ?? false,
    resolve_references: options?.resolveReferences ?? true,
    raw: options?.raw ?? false
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
