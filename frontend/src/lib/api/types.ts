export interface Project {
  slug: string;
  name: string;
  description?: string;
  createdAt?: string;
}

export interface Config {
  slug: string;
  name: string;
  parentSlug?: string;
  createdAt?: string;
}

export interface Secret {
  key: string;
  value: string;
  updatedAt?: string;
}

export interface Token {
  id: string;
  type: 'service' | 'personal';
  subject: string;
  scopes: string[];
  expiresAt?: string;
  lastUsedAt?: string;
}

export interface AuditEvent {
  id: string;
  timestamp: string;
  actor: string;
  action: string;
  projectSlug?: string;
  configSlug?: string;
  secretKey?: string;
  status: 'success' | 'failure';
}

export interface ApiError {
  message: string;
  status: number;
}

export interface CreateTokenInput {
  type: 'service' | 'personal';
  serviceName?: string;
  projectSlug?: string;
  configSlug?: string;
  access: 'read' | 'read_write';
  ttlSeconds?: number;
}

export interface CreateTokenResponse {
  token: Token;
  plaintext: string;
}

export interface BulkExportJsonResult {
  format: 'json';
  data: Record<string, string>;
}

export interface BulkExportEnvResult {
  format: 'env';
  data: string;
}

export type BulkExportResult = BulkExportJsonResult | BulkExportEnvResult;

export interface ProjectDto {
  slug?: string;
  project_slug?: string;
  name?: string;
  description?: string;
  createdAt?: string;
  created_at?: string;
}

export interface ConfigDto {
  slug?: string;
  config_slug?: string;
  name?: string;
  parent?: string;
  parentSlug?: string;
  parent_slug?: string;
  createdAt?: string;
  created_at?: string;
}

export interface TokenDto {
  id?: string;
  token_id?: string;
  jti?: string;
  type?: string;
  subject?: string;
  subject_user?: string;
  subject_service_name?: string;
  service_name?: string;
  scopes?: unknown[];
  actions?: string[];
  expiresAt?: string;
  expires_at?: string;
  lastUsedAt?: string;
  last_used_at?: string;
}

export interface ProjectsResponseDto {
  projects?: ProjectDto[];
}

export interface CreateProjectResponseDto {
  status?: string;
  project: ProjectDto;
}

export interface ConfigsResponseDto {
  configs?: ConfigDto[];
}

export interface CreateConfigResponseDto {
  status?: string;
  config: ConfigDto;
}

export interface SecretsJsonResponseDto {
  data?: Record<string, string>;
  status?: string;
}

export interface AuditEventsResponseDto {
  events?: AuditEventDto[];
  status?: string;
}

export interface TokenListResponseDto {
  tokens?: TokenDto[];
  data?: TokenDto[];
  status?: string;
}

export interface CreateTokenResponseDto {
  status?: string;
  token?: TokenDto | string;
  data?: TokenDto;
  type?: string;
  expires_at?: string;
  plaintext?: string;
  token_plaintext?: string;
  token_value?: string;
  secret?: string;
}

export type AuditEventDto = Record<string, unknown>;
