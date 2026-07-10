// Row-level DTO shapes (the ones with camelCase/snake_case guard chains)
// live in ./schemas as zod schemas -- this file keeps the domain types plus
// the thin response envelopes that wrap them.
import type {
  AuditEventDto,
  ConfigDto,
  ProjectDto,
  ReloadConfigStatusDto,
  SecretMetaDto,
  TokenDto,
  WorkspaceGroupDto,
  WorkspaceGroupMappingDto,
  WorkspaceMemberDto,
  WorkspaceProjectMemberDto
} from './schemas';

export interface Project {
  slug: string;
  name: string;
  description?: string;
  createdAt?: string;
  archived?: boolean;
}

export interface Config {
  slug: string;
  name: string;
  parentSlug?: string;
  description?: string | null;
  createdAt?: string;
}

export interface Secret {
  key: string;
  value: string;
  updatedAt?: string;
  iconSlug?: string;
  description?: string | null;
  // Absent = sensitive (masked) by default; false means shown in the clear.
  sensitive?: boolean;
  // Provenance: config slug that supplied the effective value + whether it
  // was inherited from an ancestor config (populated when export provenance
  // is requested).
  source?: string | null;
  isInherited?: boolean;
}

export interface SecretComparisonRow {
  configSlug: string;
  effective: {
    value: string | null;
    source: string | null;
    isInherited: boolean;
    sensitive?: boolean;
  };
  direct: {
    exists: boolean;
    value?: string | null;
    sensitive?: boolean;
  };
  hasIssues?: boolean;
  issues?: SecretComparisonIssue[];
  meta?: {
    updatedAt?: string | null;
    updatedBy?: string | null;
    iconSlug?: string | null;
  };
}

export interface SecretComparisonIssue {
  code: string;
  severity: 'info' | 'warning' | 'error';
  message: string;
}

export interface SecretComparisonSummary {
  uniqueEffectiveValues: number;
  missingCount: number;
  conflict: boolean;
}

export interface SecretComparisonIssueSummary {
  totalIssues: number;
  affectedConfigs: number;
  byCode: Array<{
    code: string;
    count: number;
  }>;
}

export interface SecretComparisonResult {
  project: string;
  key: string;
  configs: SecretComparisonRow[];
  summary: SecretComparisonSummary;
  issuesSummary: SecretComparisonIssueSummary;
}

export interface Token {
  id: string;
  type: 'service' | 'personal';
  subject: string;
  scopes: string[];
  createdAt?: string;
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

export interface AuditEventsPage {
  events: AuditEvent[];
  page: number;
  limit: number;
  hasNext: boolean;
}

export type ReloadInstanceOutcome = 'current' | 'updated' | 'error';
export type ReloadUnitOutcome = 'current' | 'recreated' | 'failed' | 'skipped';

export interface ReloadUnitStatus {
  id: string;
  name: string;
  heldRevision: string | null;
  outcome: ReloadUnitOutcome;
  error: string | null;
}

export interface ReloadInstanceStatus {
  host: string;
  instanceId: string;
  version: string | null;
  lastSeenAt: string;
  /** When this instance last actually reloaded the config (an "updated"
   *  cycle); null until the first real reload. */
  revisionUpdatedAt: string | null;
  trigger: string | null;
  revision: string | null;
  outcome: ReloadInstanceOutcome;
  error: string | null;
  units: ReloadUnitStatus[];
}

export interface ReloadConfigStatus {
  project: string;
  config: string;
  instances: ReloadInstanceStatus[];
}

export interface MeProfile {
  username: string;
  email?: string | null;
  fullName?: string | null;
  workspaceRole?: string | null;
  workspaceSlug?: string | null;
  effectivePermissionsSummary?: {
    globalActions: string[];
    projectScopeCount: number;
  };
}

export interface WorkspaceSettings {
  defaultWorkspaceRole: 'owner' | 'admin' | 'collaborator' | 'viewer';
  defaultProjectRole: 'admin' | 'collaborator' | 'viewer' | 'none';
  referencingEnabled: boolean;
}

export interface WorkspaceMember {
  username: string;
  email?: string | null;
  fullName?: string | null;
  workspaceRole: 'owner' | 'admin' | 'collaborator' | 'viewer';
  disabled: boolean;
  createdAt?: string;
}

export interface WorkspaceGroup {
  id: string;
  slug: string;
  name: string;
  description?: string | null;
  createdAt?: string;
}

export interface WorkspaceGroupMapping {
  id: string;
  provider: string;
  externalGroupKey: string;
  groupSlug?: string | null;
  createdAt?: string;
}

export interface WorkspaceProjectMember {
  subjectType: 'user' | 'group';
  subjectId: string;
  role: 'admin' | 'collaborator' | 'viewer' | 'none';
  groupSlug?: string | null;
}

export interface CreateTokenInput {
  type: 'service' | 'personal';
  serviceName?: string;
  projectSlug?: string;
  configSlug?: string;
  access: 'read' | 'read_write' | 'reload';
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

export interface RecomputeProjectIconsSummary {
  configsScanned: number;
  keysScanned: number;
  keysUpdated: number;
  secretsUpdated: number;
  keysSkippedManual: number;
}

export interface RecomputeProjectIconsResponseDto {
  status?: string;
  summary?: RecomputeProjectIconsSummary;
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
  meta?: Record<string, SecretMetaDto>;
  status?: string;
}

export interface AuditEventsResponseDto {
  events?: AuditEventDto[];
  page?: number;
  limit?: number;
  has_next?: boolean;
  hasNext?: boolean;
  status?: string;
}

export interface ReloadStatusResponseDto {
  status?: string;
  data?: ReloadConfigStatusDto[];
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

export interface WorkspaceMembersResponseDto {
  status?: string;
  members?: WorkspaceMemberDto[];
  member?: WorkspaceMemberDto;
}

export interface WorkspaceGroupsResponseDto {
  status?: string;
  groups?: WorkspaceGroupDto[];
  group?: WorkspaceGroupDto;
}

export interface WorkspaceGroupMembersResponseDto {
  status?: string;
  members?: string[];
}

export interface WorkspaceGroupMappingsResponseDto {
  status?: string;
  mappings?: WorkspaceGroupMappingDto[];
  mapping?: WorkspaceGroupMappingDto;
}

export interface WorkspaceProjectMembersResponseDto {
  status?: string;
  members?: WorkspaceProjectMemberDto[];
}
