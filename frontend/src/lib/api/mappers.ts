import { looseStringArray } from './schemas';
import type {
  AuditEventDto,
  ConfigDto,
  MeResponseDto,
  ProjectDto,
  ReloadConfigStatusDto,
  ReloadInstanceStatusDto,
  ReloadUnitStatusDto,
  SecretComparisonResponseDto,
  SecretComparisonRowDto,
  SecretMetaDto,
  TokenDto,
  WorkspaceGroupDto,
  WorkspaceGroupMappingDto,
  WorkspaceMemberDto,
  WorkspaceProjectMemberDto,
  WorkspaceSettingsResponseDto
} from './schemas';
import type {
  AuditEvent,
  Config,
  MeProfile,
  Project,
  ReloadConfigStatus,
  ReloadInstanceStatus,
  ReloadUnitStatus,
  SecretComparisonResult,
  SecretComparisonRow,
  Secret,
  Token,
  WorkspaceGroup,
  WorkspaceGroupMapping,
  WorkspaceMember,
  WorkspaceProjectMember,
  WorkspaceSettings
} from './types';

// Field-shape validation now happens in ./schemas (zod) at the API
// boundary; everything below is pure domain mapping -- merging whichever
// alternate field won, applying defaults, and the odd bit of business logic
// (id/action fallback chains, actions-from-scopes extraction) that doesn't
// belong in a wire-shape schema.

function fallbackId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

// Legacy scope shape: an array of scope *objects*, each carrying its own
// nested `actions` array, rather than a flat array of action strings.
function extractActionsFromScopes(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  const actions: string[] = [];
  for (const scope of value) {
    if (!scope || typeof scope !== 'object') continue;
    const fromScope = looseStringArray.parse((scope as { actions?: unknown }).actions);
    actions.push(...fromScope);
  }
  return [...new Set(actions)];
}

export function mapProjectDto(dto: ProjectDto): Project {
  const slug = dto.slug ?? dto.project_slug ?? 'unknown-project';
  return {
    slug,
    name: dto.name ?? slug,
    description: dto.description,
    createdAt: dto.createdAt ?? dto.created_at,
    archived: dto.archived
  };
}

export function mapConfigDto(dto: ConfigDto): Config {
  const slug = dto.slug ?? dto.config_slug ?? 'default';
  return {
    slug,
    name: dto.name ?? slug,
    parentSlug: dto.parent ?? dto.parentSlug ?? dto.parent_slug,
    description: dto.description ?? null,
    createdAt: dto.createdAt ?? dto.created_at
  };
}

export function mapSecretsData(
  data: Record<string, string>,
  meta?: Record<string, SecretMetaDto>
): Secret[] {
  return Object.entries(data)
    .map(([key, value]) => {
      const entry = meta?.[key];
      return {
        key,
        value,
        updatedAt: entry?.updatedAt,
        iconSlug: entry?.iconSlug,
        description: entry?.description ?? null,
        // Absence (or a malformed non-boolean value) means sensitive
        // (masked) by default -- a pinned security contract, so this reads
        // the raw field directly rather than through a tolerant-boolean
        // schema that could quietly normalize a bad value to `false`.
        sensitive: (entry?.sensitive as boolean | undefined) ?? true,
        source: entry?.source ?? null,
        isInherited: entry?.isInherited ?? false
      };
    })
    .sort((a, b) => a.key.localeCompare(b.key));
}

export function mapTokenDto(dto: TokenDto): Token {
  const id = dto.id ?? dto.token_id ?? dto.jti ?? fallbackId('token');
  const type = dto.type === 'service' ? 'service' : 'personal';
  const actions = dto.actions;
  const scopes =
    actions.length > 0
      ? actions
      : extractActionsFromScopes(dto.scopes).length > 0
        ? extractActionsFromScopes(dto.scopes)
        : looseStringArray.parse(dto.scopes);

  return {
    id,
    type,
    subject:
      dto.subject ??
      dto.subject_service_name ??
      dto.subject_user ??
      dto.service_name ??
      id,
    scopes,
    createdAt: dto.createdAt ?? dto.created_at,
    expiresAt: dto.expiresAt ?? dto.expires_at,
    lastUsedAt: dto.lastUsedAt ?? dto.last_used_at
  };
}

function statusFromEvent(dto: AuditEventDto): 'success' | 'failure' {
  const statusCode = dto.status_code;
  if (typeof statusCode === 'number') {
    return statusCode < 400 ? 'success' : 'failure';
  }

  if (dto.status === 'success' || dto.status === 'ok' || dto.status === 'OK') {
    return 'success';
  }
  if (dto.status === 'failure' || dto.status === 'error') {
    return 'failure';
  }

  return 'success';
}

export function mapAuditEventDto(dto: AuditEventDto): AuditEvent {
  const timestamp =
    dto.ts ?? dto.timestamp ?? dto.time ?? dto.created_at ?? dto.createdAt ?? new Date().toISOString();

  const action = dto.action ?? dto.event ?? dto.type ?? dto.method ?? 'unknown';

  const actor = dto.actor_id ?? dto.actor ?? dto.user ?? 'unknown';
  const projectSlug = dto.project_slug ?? dto.project ?? dto.projectSlug;
  const configSlug = dto.config_slug ?? dto.config ?? dto.configSlug;
  const secretKey = dto.key ?? dto.secret_key ?? dto.secretKey;

  const id =
    dto.id ??
    dto.event_id ??
    dto.request_id ??
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

export function mapReloadUnitStatusDto(dto: ReloadUnitStatusDto): ReloadUnitStatus {
  return {
    id: dto.id ?? dto.unit_id ?? fallbackId('unit'),
    name: dto.name ?? dto.unit_name ?? 'unknown',
    heldRevision: dto.heldRevision ?? dto.held_revision ?? null,
    outcome: dto.outcome,
    error: dto.error ?? null
  };
}

export function mapReloadInstanceStatusDto(dto: ReloadInstanceStatusDto): ReloadInstanceStatus {
  return {
    host: dto.host ?? dto.hostname ?? 'unknown-host',
    instanceId: dto.instanceId ?? dto.instance_id ?? fallbackId('instance'),
    version: dto.version ?? null,
    lastSeenAt: dto.lastSeenAt ?? dto.last_seen_at ?? new Date(0).toISOString(),
    revisionUpdatedAt: dto.revisionUpdatedAt ?? null,
    trigger: dto.trigger ?? null,
    revision: dto.revision ?? null,
    outcome: dto.outcome,
    error: dto.error ?? null,
    units: (dto.units ?? []).map(mapReloadUnitStatusDto)
  };
}

export function mapReloadConfigStatusDto(dto: ReloadConfigStatusDto): ReloadConfigStatus {
  return {
    project: dto.project ?? dto.project_slug ?? 'unknown-project',
    config: dto.config ?? dto.config_slug ?? 'unknown-config',
    instances: (dto.instances ?? []).map(mapReloadInstanceStatusDto)
  };
}

export function mapAccessToActions(access: 'read' | 'read_write' | 'reload'): string[] {
  if (access === 'read_write') {
    return ['secrets:read', 'secrets:export', 'secrets:write'];
  }
  if (access === 'reload') {
    // The ssm-reload sidecar needs BOTH secrets:export (conditional config
    // export) and reload:report (POST reload events + the per-cycle fleet
    // status). Without a preset that carries reload:report there is no way to
    // mint a working reloader token from the console -- read/read_write both
    // omit it. reload:report is service-token-only (never in an RBAC role map,
    // see ssm_server/access/scopes.py), so this preset is offered for service
    // tokens only. Mirrors docs/SECRETS_RELOADER.md step 1.
    return ['secrets:read', 'secrets:export', 'reload:report'];
  }
  return ['secrets:read', 'secrets:export'];
}

function mapSecretComparisonRowDto(dto: SecretComparisonRowDto): SecretComparisonRow {
  const issues = (dto.issues ?? [])
    .map((issue) => ({
      code: issue.code ?? 'unknown_issue',
      severity: issue.severity,
      message: issue.message ?? 'Unknown issue'
    }))
    .filter((issue) => issue.code !== 'unknown_issue' || issue.message !== 'Unknown issue');

  return {
    configSlug: dto.configSlug ?? 'unknown',
    effective: {
      value: dto.effective?.value ?? null,
      source: dto.effective?.source ?? null,
      isInherited: dto.effective?.isInherited ?? false,
      sensitive: dto.effective?.sensitive ?? true
    },
    direct: {
      exists: dto.direct?.exists ?? false,
      value: dto.direct?.value ?? null,
      sensitive: dto.direct?.sensitive ?? true
    },
    hasIssues: dto.hasIssues ?? issues.length > 0,
    issues,
    meta: dto.meta
      ? {
          updatedAt: dto.meta.updatedAt ?? null,
          updatedBy: dto.meta.updatedBy ?? null,
          iconSlug: dto.meta.iconSlug ?? null
        }
      : undefined
  };
}

export function mapSecretComparisonResponse(dto: SecretComparisonResponseDto): SecretComparisonResult {
  const byCode = (dto.issuesSummary?.byCode ?? [])
    .map((entry) => ({
      code: entry.code ?? '',
      count: Number(entry.count ?? 0)
    }))
    .filter((entry) => entry.code.length > 0);

  return {
    project: dto.project ?? 'unknown-project',
    key: dto.key ?? '',
    configs: (dto.configs ?? []).map(mapSecretComparisonRowDto),
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
    username: dto.username ?? 'unknown',
    email: dto.email ?? null,
    fullName: dto.fullName ?? dto.full_name ?? null,
    workspaceRole: dto.workspaceRole ?? dto.workspace_role ?? null,
    workspaceSlug: dto.workspaceSlug ?? dto.workspace_slug ?? null,
    effectivePermissionsSummary: {
      globalActions: dto.effectivePermissionsSummary?.globalActions ?? [],
      projectScopeCount: Number(dto.effectivePermissionsSummary?.projectScopeCount ?? 0)
    }
  };
}

export function mapWorkspaceSettingsResponseDto(dto: WorkspaceSettingsResponseDto): WorkspaceSettings {
  return {
    defaultWorkspaceRole:
      (dto.settings?.defaultWorkspaceRole as WorkspaceSettings['defaultWorkspaceRole']) ?? 'viewer',
    defaultProjectRole:
      (dto.settings?.defaultProjectRole as WorkspaceSettings['defaultProjectRole']) ?? 'none',
    referencingEnabled: Boolean(dto.settings?.referencingEnabled)
  };
}

export function mapWorkspaceMemberDto(dto: WorkspaceMemberDto): WorkspaceMember {
  return {
    username: dto.username ?? 'unknown',
    email: dto.email ?? null,
    fullName: dto.fullName ?? dto.full_name ?? null,
    workspaceRole:
      (dto.workspaceRole as WorkspaceMember['workspaceRole']) ??
      (dto.workspace_role as WorkspaceMember['workspaceRole']) ??
      'viewer',
    disabled: Boolean(dto.disabled),
    createdAt: dto.createdAt ?? dto.created_at
  };
}

export function mapWorkspaceGroupDto(dto: WorkspaceGroupDto): WorkspaceGroup {
  const fallback = dto.slug ?? `group-${Date.now()}`;
  return {
    id: dto.id ?? dto._id ?? fallback,
    slug: dto.slug ?? 'unknown',
    name: dto.name ?? dto.slug ?? 'unknown',
    description: dto.description ?? null,
    createdAt: dto.createdAt ?? dto.created_at
  };
}

export function mapWorkspaceGroupMappingDto(dto: WorkspaceGroupMappingDto): WorkspaceGroupMapping {
  return {
    id: dto.id ?? dto._id ?? fallbackId('mapping'),
    provider: dto.provider ?? 'manual',
    externalGroupKey: dto.externalGroupKey ?? dto.external_group_key ?? '',
    groupSlug: dto.groupSlug ?? dto.group_slug ?? null,
    createdAt: dto.createdAt ?? dto.created_at
  };
}

export function mapWorkspaceProjectMemberDto(dto: WorkspaceProjectMemberDto): WorkspaceProjectMember {
  return {
    subjectType: ((dto.subjectType ?? dto.subject_type) as WorkspaceProjectMember['subjectType']) ?? 'user',
    subjectId: dto.subjectId ?? dto.subject_id ?? '',
    role: (dto.role as WorkspaceProjectMember['role']) ?? 'none',
    groupSlug: dto.groupSlug ?? dto.group_slug ?? null
  };
}
