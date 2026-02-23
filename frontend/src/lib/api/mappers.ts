import type {
  AuditEvent,
  AuditEventDto,
  Config,
  ConfigDto,
  Project,
  ProjectDto,
  Secret,
  Token,
  TokenDto
} from './types';

function asString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value : undefined;
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

export function mapSecretsData(data: Record<string, string>): Secret[] {
  return Object.entries(data)
    .map(([key, value]) => ({
      key,
      value,
      updatedAt: undefined
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
