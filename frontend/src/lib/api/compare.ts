import { apiClient } from './client';
import { mapSecretComparisonResponse } from './mappers';
import type { SecretComparisonResponseDto, SecretComparisonResult } from './types';

export interface SecretCompareOptions {
  includeParent?: boolean;
  includeMeta?: boolean;
  includeEmpty?: boolean;
  resolveReferences?: boolean;
  raw?: boolean;
  limitConfigs?: number;
}

export async function getSecretComparison(
  projectSlug: string,
  key: string,
  options?: SecretCompareOptions
): Promise<SecretComparisonResult> {
  const params = new URLSearchParams({
    include_parent: String(options?.includeParent ?? true),
    include_meta: String(options?.includeMeta ?? true),
    include_empty: String(options?.includeEmpty ?? true),
    resolve_references: String(options?.resolveReferences ?? true),
    raw: String(options?.raw ?? false),
    limit_configs: String(options?.limitConfigs ?? 200)
  });
  const response = await apiClient<SecretComparisonResponseDto>(
    `/projects/${projectSlug}/compare/secrets/${encodeURIComponent(key)}?${params.toString()}`
  );
  return mapSecretComparisonResponse(response);
}
