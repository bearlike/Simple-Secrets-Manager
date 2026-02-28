import type {
  AuditEvent,
  AuditEventDto,
  Config,
  ConfigDto,
  MeProfile,
  MeResponseDto,
  Project,
  ProjectDto,
  SecretComparisonResponseDto,
  SecretComparisonResult,
  SecretComparisonRow,
  SecretComparisonRowDto,
  SecretMetaDto,
  Secret,
  Token,
  TokenDto,
  WorkspaceGroup,
  WorkspaceGroupDto,
  WorkspaceGroupMapping,
  WorkspaceGroupMappingDto,
  WorkspaceMember,
  WorkspaceMemberDto,
  WorkspaceProjectMember,
  WorkspaceProjectMemberDto,
  WorkspaceSettings,
  WorkspaceSettingsResponseDto
} from './types';

function asString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value : undefined;
}

function asBoolean(value: unknown): boolean | undefined {
  return typeof value === 'boolean' ? value : undefined;
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0);
}

function extractActionsFromScopes(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  const actions: string[] = [];
  for (const scope of value) {
    if (!scope || typeof scope !== 'object') continue;
    const fromScope = asStringArray((scope as { actions?: unknown }).actions);
    actions.push(...fromScope);
  }
  return [...new Set(actions)];
}

function fallbackId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function mapProjectDto(dto: ProjectDto): Project {
  const slug = asString(dto.slug) ?? asString(dto.project_slug) ?? 'unknown-project';
  return {
    slug,
    name: asString(dto.name) ?? slug,
    description: asString(dto.description),
    createdAt: asString(dto.createdAt) ?? asString(dto.created_at)
  };
}

export function mapConfigDto(dto: ConfigDto): Config {
  const slug = asString(dto.slug) ?? asString(dto.config_slug) ?? 'default';
  return {
    slug,
    name: asString(dto.name) ?? slug,
    parentSlug: asString(dto.parent) ?? asString(dto.parentSlug) ?? asString(dto.parent_slug),
    createdAt: asString(dto.createdAt) ?? asString(dto.created_at)
  };
}

export function mapSecretsData(
  data: Record<string, string>,
  meta?: Record<string, SecretMetaDto>
): Secret[] {
  return Object.entries(data)
    .map(([key, value]) => ({
      key,
      value,
      updatedAt: asString(meta?.[key]?.updatedAt),
      iconSlug: asString(meta?.[key]?.iconSlug) ?? asString(meta?.[key]?.icon_slug)
    }))
    .sort((a, b) => a.key.localeCompare(b.key));
}

export function mapTokenDto(dto: TokenDto): Token {
  const id = asString(dto.id) ?? asString(dto.token_id) ?? asString(dto.jti) ?? fallbackId('token');
  const type = dto.type === 'service' ? 'service' : 'personal';
  const actions = asStringArray(dto.actions);
  const scopes =
    actions.length > 0
      ? actions
      : extractActionsFromScopes(dto.scopes).length > 0
        ? extractActionsFromScopes(dto.scopes)
        : asStringArray(dto.scopes);

  return {
    id,
    type,
    subject:
      asString(dto.subject) ??
      asString(dto.subject_service_name) ??
      asString(dto.subject_user) ??
      asString(dto.service_name) ??
      id,
    scopes,
    createdAt: asString(dto.createdAt) ?? asString(dto.created_at),
    expiresAt: asString(dto.expiresAt) ?? asString(dto.expires_at),
    lastUsedAt: asString(dto.lastUsedAt) ?? asString(dto.last_used_at)
  };
}

function statusFromEvent(dto: AuditEventDto): 'success' | 'failure' {
  const statusCode = dto.status_code;
  if (typeof statusCode === 'number') {
    return statusCode < 400 ? 'success' : 'failure';
  }

  const explicitStatus = asString(dto.status);
  if (explicitStatus === 'success' || explicitStatus === 'ok' || explicitStatus === 'OK') {
    return 'success';
  }
  if (explicitStatus === 'failure' || explicitStatus === 'error') {
    return 'failure';
  }

  return 'success';
}

export function mapAuditEventDto(dto: AuditEventDto): AuditEvent {
  const timestamp =
    asString(dto.ts) ??
    asString(dto.timestamp) ??
    asString(dto.time) ??
    asString(dto.created_at) ??
    asString(dto.createdAt) ??
    new Date().toISOString();

  const action =
    asString(dto.action) ??
    asString(dto.event) ??
    asString(dto.type) ??
    asString(dto.method) ??
    'unknown';

  const actor = asString(dto.actor_id) ?? asString(dto.actor) ?? asString(dto.user) ?? 'unknown';
  const projectSlug = asString(dto.project_slug) ?? asString(dto.project) ?? asString(dto.projectSlug);
  const configSlug = asString(dto.config_slug) ?? asString(dto.config) ?? asString(dto.configSlug);
  const secretKey = asString(dto.key) ?? asString(dto.secret_key) ?? asString(dto.secretKey);

  const id =
    asString(dto.id) ??
    asString(dto.event_id) ??
    asString(dto.request_id) ??
    `${timestamp}:${action}:${actor}:${projectSlug ?? ''}:${configSlug ?? ''}:${secretKey ?? ''}`;

  return {
    id,
    timestamp,
    actor,
    action,
    projectSlug,
    configSlug,
    secretKey,
    status: statusFromEvent(dto)
  };
}

export function mapAccessToActions(access: 'read' | 'read_write'): string[] {
  if (access === 'read_write') {
    return ['secrets:read', 'secrets:export', 'secrets:write'];
  }
  return ['secrets:read', 'secrets:export'];
}

function mapSecretComparisonRowDto(dto: SecretComparisonRowDto): SecretComparisonRow {
  const issues = Array.isArray(dto.issues)
    ? dto.issues
        .map((issue) => ({
          code: asString(issue.code) ?? 'unknown_issue',
          severity: (asString(issue.severity) as 'info' | 'warning' | 'error' | undefined) ?? 'warning',
          message: asString(issue.message) ?? 'Unknown issue'
        }))
        .filter((issue) => issue.code !== 'unknown_issue' || issue.message !== 'Unknown issue')
    : [];

  return {
    configSlug: asString(dto.configSlug) ?? asString(dto.config_slug) ?? 'unknown',
    effective: {
      value:
        typeof dto.effective?.value === 'string' || dto.effective?.value === null ? dto.effective.value : null,
      source:
        typeof dto.effective?.source === 'string' || dto.effective?.source === null ? dto.effective.source : null,
      isInherited: asBoolean(dto.effective?.isInherited) ?? asBoolean(dto.effective?.is_inherited) ?? false
    },
    direct: {
      exists: asBoolean(dto.direct?.exists) ?? false,
      value: typeof dto.direct?.value === 'string' || dto.direct?.value === null ? dto.direct.value : null
    },
    hasIssues: asBoolean(dto.hasIssues) ?? asBoolean(dto.has_issues) ?? issues.length > 0,
    issues,
    meta: dto.meta ?
    {
      updatedAt: asString(dto.meta.updatedAt) ?? asString(dto.meta.updated_at) ?? null,
      updatedBy: asString(dto.meta.updatedBy) ?? asString(dto.meta.updated_by) ?? null,
      iconSlug: asString(dto.meta.iconSlug) ?? asString(dto.meta.icon_slug) ?? null
    } :
    undefined
  };
}

export function mapSecretComparisonResponse(dto: SecretComparisonResponseDto): SecretComparisonResult {
  const byCode = Array.isArray(dto.issuesSummary?.byCode)
    ? dto.issuesSummary.byCode
        .map((entry) => ({
          code: asString(entry.code) ?? '',
          count: Number(entry.count ?? 0)
        }))
        .filter((entry) => entry.code.length > 0)
    : [];

  return {
    project: asString(dto.project) ?? 'unknown-project',
    key: asString(dto.key) ?? '',
    configs: Array.isArray(dto.configs) ? dto.configs.map(mapSecretComparisonRowDto) : [],
    summary: {
      uniqueEffectiveValues: Number(dto.summary?.uniqueEffectiveValues ?? 0),
      missingCount: Number(dto.summary?.missingCount ?? 0),
      conflict: Boolean(dto.summary?.conflict ?? false)
    },
    issuesSummary: {
      totalIssues: Number(dto.issuesSummary?.totalIssues ?? 0),
      affectedConfigs: Number(dto.issuesSummary?.affectedConfigs ?? 0),
      byCode
    }
  };
}

export function mapMeResponseDto(dto: MeResponseDto): MeProfile {
  return {
    username: asString(dto.username) ?? 'unknown',
    email: asString(dto.email) ?? null,
    fullName: asString(dto.fullName) ?? asString(dto.full_name) ?? null,
    workspaceRole: asString(dto.workspaceRole) ?? asString(dto.workspace_role) ?? null,
    workspaceSlug: asString(dto.workspaceSlug) ?? asString(dto.workspace_slug) ?? null,
    effectivePermissionsSummary: {
      globalActions: asStringArray(dto.effectivePermissionsSummary?.globalActions),
      projectScopeCount: Number(dto.effectivePermissionsSummary?.projectScopeCount ?? 0)
    }
  };
}

export function mapWorkspaceSettingsResponseDto(dto: WorkspaceSettingsResponseDto): WorkspaceSettings {
  return {
    defaultWorkspaceRole:
      (asString(dto.settings?.defaultWorkspaceRole) as WorkspaceSettings['defaultWorkspaceRole']) ?? 'viewer',
    defaultProjectRole:
      (asString(dto.settings?.defaultProjectRole) as WorkspaceSettings['defaultProjectRole']) ?? 'none',
    referencingEnabled: Boolean(dto.settings?.referencingEnabled)
  };
}

export function mapWorkspaceMemberDto(dto: WorkspaceMemberDto): WorkspaceMember {
  return {
    username: asString(dto.username) ?? 'unknown',
    email: asString(dto.email) ?? null,
    fullName: asString(dto.fullName) ?? asString(dto.full_name) ?? null,
    workspaceRole:
      (asString(dto.workspaceRole) as WorkspaceMember['workspaceRole']) ??
      (asString(dto.workspace_role) as WorkspaceMember['workspaceRole']) ??
      'viewer',
    disabled: Boolean(dto.disabled),
    createdAt: asString(dto.createdAt) ?? asString(dto.created_at)
  };
}

export function mapWorkspaceGroupDto(dto: WorkspaceGroupDto): WorkspaceGroup {
  const fallbackId = asString(dto.slug) ?? `group-${Date.now()}`;
  return {
    id: asString(dto.id) ?? asString(dto._id) ?? fallbackId,
    slug: asString(dto.slug) ?? 'unknown',
    name: asString(dto.name) ?? asString(dto.slug) ?? 'unknown',
    description: asString(dto.description) ?? null,
    createdAt: asString(dto.createdAt) ?? asString(dto.created_at)
  };
}

export function mapWorkspaceGroupMappingDto(dto: WorkspaceGroupMappingDto): WorkspaceGroupMapping {
  return {
    id: asString(dto.id) ?? asString(dto._id) ?? fallbackId('mapping'),
    provider: asString(dto.provider) ?? 'manual',
    externalGroupKey: asString(dto.externalGroupKey) ?? asString(dto.external_group_key) ?? '',
    groupSlug: asString(dto.groupSlug) ?? asString(dto.group_slug) ?? null,
    createdAt: asString(dto.createdAt) ?? asString(dto.created_at)
  };
}

export function mapWorkspaceProjectMemberDto(dto: WorkspaceProjectMemberDto): WorkspaceProjectMember {
  return {
    subjectType:
      ((asString(dto.subjectType) ?? asString(dto.subject_type)) as WorkspaceProjectMember['subjectType']) ?? 'user',
    subjectId: asString(dto.subjectId) ?? asString(dto.subject_id) ?? '',
    role: (asString(dto.role) as WorkspaceProjectMember['role']) ?? 'none',
    groupSlug: asString(dto.groupSlug) ?? asString(dto.group_slug) ?? null
  };
}
