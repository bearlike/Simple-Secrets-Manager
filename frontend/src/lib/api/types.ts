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
  iconSlug?: string;
}

export interface SecretComparisonRow {
  configSlug: string;
  effective: {
    value: string | null;
    source: string | null;
    isInherited: boolean;
  };
  direct: {
    exists: boolean;
    value?: string | null;
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

export interface ApiError {
  message: string;
  status: number;
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
  createdAt?: string;
  created_at?: string;
  lastUsedAt?: string;
  last_used_at?: string;
  revokedAt?: string;
  revoked_at?: string;
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

export interface SecretMetaDto {
  updatedAt?: string;
  updated_by?: string;
  updatedBy?: string;
  iconSlug?: string;
  icon_slug?: string;
}

export interface SecretComparisonRowDto {
  configSlug?: string;
  config_slug?: string;
  effective?: {
    value?: string | null;
    source?: string | null;
    isInherited?: boolean;
    is_inherited?: boolean;
  };
  direct?: {
    exists?: boolean;
    value?: string | null;
  };
  hasIssues?: boolean;
  has_issues?: boolean;
  issues?: Array<{
    code?: string;
    severity?: string;
    message?: string;
  }>;
  meta?: {
    updatedAt?: string | null;
    updated_at?: string | null;
    updatedBy?: string | null;
    updated_by?: string | null;
    iconSlug?: string | null;
    icon_slug?: string | null;
  };
}

export interface SecretComparisonResponseDto {
  status?: string;
  project?: string;
  key?: string;
  configs?: SecretComparisonRowDto[];
  summary?: {
    uniqueEffectiveValues?: number;
    missingCount?: number;
    conflict?: boolean;
  };
  issuesSummary?: {
    totalIssues?: number;
    affectedConfigs?: number;
    byCode?: Array<{
      code?: string;
      count?: number;
    }>;
  };
}

export interface AuditEventsResponseDto {
  events?: AuditEventDto[];
  page?: number;
  limit?: number;
  has_next?: boolean;
  hasNext?: boolean;
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

export interface MeResponseDto {
  status?: string;
  username?: string;
  email?: string | null;
  fullName?: string | null;
  full_name?: string | null;
  workspaceRole?: string | null;
  workspace_role?: string | null;
  workspaceSlug?: string | null;
  workspace_slug?: string | null;
  effectivePermissionsSummary?: {
    globalActions?: string[];
    projectScopeCount?: number;
  };
}

export interface WorkspaceSettingsResponseDto {
  status?: string;
  settings?: {
    defaultWorkspaceRole?: string;
    defaultProjectRole?: string;
    referencingEnabled?: boolean;
  };
}

export interface WorkspaceMemberDto {
  username?: string;
  email?: string | null;
  fullName?: string | null;
  full_name?: string | null;
  workspaceRole?: string;
  workspace_role?: string;
  disabled?: boolean;
  createdAt?: string;
  created_at?: string;
}

export interface WorkspaceMembersResponseDto {
  status?: string;
  members?: WorkspaceMemberDto[];
  member?: WorkspaceMemberDto;
}

export interface WorkspaceGroupDto {
  id?: string;
  _id?: string;
  slug?: string;
  name?: string;
  description?: string | null;
  createdAt?: string;
  created_at?: string;
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

export interface WorkspaceGroupMappingDto {
  id?: string;
  _id?: string;
  provider?: string;
  externalGroupKey?: string;
  external_group_key?: string;
  groupSlug?: string | null;
  group_slug?: string | null;
  createdAt?: string;
  created_at?: string;
}

export interface WorkspaceGroupMappingsResponseDto {
  status?: string;
  mappings?: WorkspaceGroupMappingDto[];
  mapping?: WorkspaceGroupMappingDto;
}

export interface WorkspaceProjectMemberDto {
  subjectType?: string;
  subject_type?: string;
  subjectId?: string;
  subject_id?: string;
  role?: string;
  groupSlug?: string | null;
  group_slug?: string | null;
}

export interface WorkspaceProjectMembersResponseDto {
  status?: string;
  members?: WorkspaceProjectMemberDto[];
}
