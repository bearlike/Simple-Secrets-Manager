// zod schemas for API response DTOs -- this file IS the wire-shape
// documentation: every field a backend endpoint can send, and exactly which
// legacy/alternate spellings we still tolerate. See `frontend/AGENTS.md` for
// the "zod at the boundary" convention this file establishes.
//
// Every schema is built from the four `loose*` primitives below, which are
// the direct zod equivalents of the old `asString`/`asBoolean`/
// `asStringArray` guard-chain helpers: a field of the wrong runtime type
// degrades to `undefined` (or `[]` for arrays) instead of failing
// validation. Backend responses are untrusted input that may be malformed
// or mid-migration -- one bad field must never crash a page.
import { z } from 'zod';
import type { ReloadInstanceOutcome, ReloadUnitOutcome } from './types';

export const looseString = z.unknown().transform((value) =>
  typeof value === 'string' && value.trim() ? value : undefined
);

export const looseBoolean = z.unknown().transform((value) =>
  typeof value === 'boolean' ? value : undefined
);

export const looseStringArray = z.unknown().transform((value) =>
  Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    : []
);

/**
 * Parse a raw (unknown-shaped) array into `T[]`, silently dropping any
 * element that fails validation instead of aborting the whole collection --
 * one malformed row (a stray `null`, a half-migrated shape) must not blank
 * out an entire table.
 */
export function parseListSafely<T>(schema: z.ZodType<T, z.ZodTypeDef, unknown>, items: unknown): T[] {
  if (!Array.isArray(items)) return [];
  const parsed: T[] = [];
  for (const item of items) {
    const result = schema.safeParse(item);
    if (result.success) parsed.push(result.data);
  }
  return parsed;
}

/**
 * Same fail-soft contract as `parseListSafely`, for dictionary-shaped
 * fields (e.g. secrets metadata keyed by secret key) rather than arrays.
 */
export function parseRecordSafely<T>(schema: z.ZodType<T, z.ZodTypeDef, unknown>, value: unknown): Record<string, T> {
  const result: Record<string, T> = {};
  if (!value || typeof value !== 'object') return result;
  for (const [key, entry] of Object.entries(value as Record<string, unknown>)) {
    const parsed = schema.safeParse(entry);
    if (parsed.success) result[key] = parsed.data;
  }
  return result;
}

// ---------------------------------------------------------------------
// Dual-emit family: projects list, configs CREATE response, tokens list.
// The server currently emits snake_case (created_at, expires_at,
// last_used_at) while a parallel backend track adds camelCase alongside.
// Accept camelCase primary WITH a snake_case fallback for exactly these
// three families -- each snake field below is commented at the point it's
// read, so the fallback is easy to find and delete once the migration
// finishes.
// ---------------------------------------------------------------------

export const projectDtoSchema = z.object({
  slug: looseString,
  project_slug: looseString,
  name: looseString,
  description: looseString,
  createdAt: looseString,
  created_at: looseString, // server dual-emits; snake fallback removable next major
  // Plain truthy coercion (`Boolean(x)`), matching the original
  // `Boolean(dto.archived)` -- not a strict typeof-boolean check, and no
  // dual-emit concern since there's only ever one spelling of this field.
  archived: z.unknown().transform((value) => Boolean(value))
});
export type ProjectDto = z.infer<typeof projectDtoSchema>;

export const configDtoSchema = z.object({
  slug: looseString,
  config_slug: looseString,
  name: looseString,
  parent: looseString,
  parentSlug: looseString,
  parent_slug: looseString,
  description: looseString,
  createdAt: looseString,
  created_at: looseString // server dual-emits; snake fallback removable next major
});
export type ConfigDto = z.infer<typeof configDtoSchema>;

export const tokenDtoSchema = z.object({
  id: looseString,
  token_id: looseString,
  jti: looseString,
  type: looseString,
  subject: looseString,
  subject_user: looseString,
  subject_service_name: looseString,
  service_name: looseString,
  // Kept raw (not run through `looseStringArray`): a legacy shape carries
  // an array of scope *objects* (each with a nested `actions` array), not
  // plain strings, so the mapper needs the untouched value to destructure
  // via `extractActionsFromScopes` before falling back to a flat string
  // array read.
  scopes: z.unknown(),
  actions: looseStringArray,
  expiresAt: looseString,
  expires_at: looseString, // server dual-emits; snake fallback removable next major
  createdAt: looseString,
  created_at: looseString, // server dual-emits; snake fallback removable next major
  lastUsedAt: looseString,
  last_used_at: looseString, // server dual-emits; snake fallback removable next major
  revokedAt: looseString,
  revoked_at: looseString
});
export type TokenDto = z.infer<typeof tokenDtoSchema>;

// ---------------------------------------------------------------------
// Pure camelCase family: comparison rows + secrets export meta. Verified
// wire shape is camelCase-only (configSlug, isInherited, sensitive,
// updatedBy, iconSlug) -- the snake_case fallbacks that used to sit
// alongside these were dead and are dropped here, not ported.
// ---------------------------------------------------------------------

export const secretMetaDtoSchema = z.object({
  updatedAt: looseString,
  updatedBy: looseString,
  iconSlug: looseString,
  description: looseString,
  // Deliberately NOT run through `looseBoolean`: absence must default to
  // `true` (masked) even if the raw value is a malformed non-boolean --
  // this is a pinned security contract (see frontend/AGENTS.md), so the
  // raw value is preserved verbatim for the mapper's `?? true` to apply.
  sensitive: z.unknown(),
  source: looseString,
  isInherited: looseBoolean
});
export type SecretMetaDto = z.infer<typeof secretMetaDtoSchema>;

const comparisonSideValue = z.unknown().transform((value) =>
  typeof value === 'string' || value === null ? value : null
);

export const secretComparisonRowDtoSchema = z.object({
  configSlug: looseString,
  effective: z
    .object({
      value: comparisonSideValue,
      source: comparisonSideValue,
      isInherited: looseBoolean,
      sensitive: looseBoolean
    })
    .optional(),
  direct: z
    .object({
      exists: looseBoolean,
      value: comparisonSideValue,
      sensitive: looseBoolean
    })
    .optional(),
  hasIssues: looseBoolean,
  issues: z
    .array(
      z.object({
        code: looseString,
        severity: z.unknown().transform((value): 'info' | 'warning' | 'error' =>
          value === 'info' || value === 'warning' || value === 'error' ? value : 'warning'
        ),
        message: looseString
      })
    )
    .optional(),
  meta: z
    .object({
      updatedAt: looseString,
      updatedBy: looseString,
      iconSlug: looseString
    })
    .optional()
});
export type SecretComparisonRowDto = z.infer<typeof secretComparisonRowDtoSchema>;

const numberLike = z.unknown();

export const secretComparisonResponseDtoSchema = z.object({
  project: looseString,
  key: looseString,
  configs: z.array(secretComparisonRowDtoSchema).optional(),
  summary: z
    .object({
      uniqueEffectiveValues: numberLike,
      missingCount: numberLike,
      conflict: z.unknown()
    })
    .optional(),
  issuesSummary: z
    .object({
      totalIssues: numberLike,
      affectedConfigs: numberLike,
      byCode: z
        .array(
          z.object({
            code: looseString,
            count: numberLike
          })
        )
        .optional()
    })
    .optional()
});
export type SecretComparisonResponseDto = z.infer<typeof secretComparisonResponseDtoSchema>;

// ---------------------------------------------------------------------
// Heterogeneous family: audit events. The event shape varies by action
// type, so known fields are typed and everything else passes through
// untouched -- replaces the old `AuditEventDto = Record<string, unknown>`
// escape hatch with a narrowed-but-still-open type.
// ---------------------------------------------------------------------

export const auditEventDtoSchema = z
  .object({
    id: looseString,
    event_id: looseString,
    request_id: looseString,
    ts: looseString,
    timestamp: looseString,
    time: looseString,
    created_at: looseString,
    createdAt: looseString,
    action: looseString,
    event: looseString,
    type: looseString,
    method: looseString,
    actor_id: looseString,
    actor: looseString,
    user: looseString,
    project_slug: looseString,
    project: looseString,
    projectSlug: looseString,
    config_slug: looseString,
    config: looseString,
    configSlug: looseString,
    key: looseString,
    secret_key: looseString,
    secretKey: looseString,
    status_code: z.unknown().transform((value) => (typeof value === 'number' ? value : undefined)),
    status: looseString
  })
  .passthrough();
export type AuditEventDto = z.infer<typeof auditEventDtoSchema>;

// ---------------------------------------------------------------------
// Reload status: camelCase per `ssm_contracts` (the Pydantic leaf shared by
// server + reloader uses `alias_generator=to_camel`). Already
// tolerant-mapped before this change -- ported to zod as-is, including the
// legacy alternate field names, rather than re-deriving which ones are
// truly dead.
// ---------------------------------------------------------------------

// Unknown/future outcome values (e.g. a newer reloader version reporting a
// status this build doesn't know about yet) degrade to 'current' rather
// than being flagged as an error -- an unrecognized status shouldn't read
// as alarming. `ssm_contracts` enforces the enum server-side, so this is a
// defensive default for version skew, not a real data-loss path.
const reloadInstanceOutcome = z.unknown().transform((value): ReloadInstanceOutcome =>
  value === 'updated' || value === 'error' ? value : 'current'
);
const reloadUnitOutcome = z.unknown().transform((value): ReloadUnitOutcome =>
  value === 'recreated' || value === 'failed' || value === 'skipped' ? value : 'current'
);

export const reloadUnitStatusDtoSchema = z.object({
  id: looseString,
  unit_id: looseString,
  name: looseString,
  unit_name: looseString,
  heldRevision: looseString,
  held_revision: looseString,
  outcome: reloadUnitOutcome,
  error: looseString
});
export type ReloadUnitStatusDto = z.infer<typeof reloadUnitStatusDtoSchema>;

export const reloadInstanceStatusDtoSchema = z.object({
  host: looseString,
  hostname: looseString,
  instanceId: looseString,
  instance_id: looseString,
  version: looseString,
  lastSeenAt: looseString,
  last_seen_at: looseString,
  revisionUpdatedAt: looseString,
  trigger: looseString,
  revision: looseString,
  outcome: reloadInstanceOutcome,
  error: looseString,
  units: z.array(reloadUnitStatusDtoSchema).optional()
});
export type ReloadInstanceStatusDto = z.infer<typeof reloadInstanceStatusDtoSchema>;

export const reloadConfigStatusDtoSchema = z.object({
  project: looseString,
  project_slug: looseString,
  config: looseString,
  config_slug: looseString,
  instances: z.array(reloadInstanceStatusDtoSchema).optional()
});
export type ReloadConfigStatusDto = z.infer<typeof reloadConfigStatusDtoSchema>;

// ---------------------------------------------------------------------
// Unverified-but-tolerant family: workspace/me endpoints. These already
// carry camelCase + snake_case fallbacks in the old mapper code, but this
// audit did not verify whether the snake side is still live -- so they're
// ported 1:1 (no drop, no dual-emit comment) rather than guessed at.
// ---------------------------------------------------------------------

export const meResponseDtoSchema = z.object({
  username: looseString,
  email: looseString,
  fullName: looseString,
  full_name: looseString,
  workspaceRole: looseString,
  workspace_role: looseString,
  workspaceSlug: looseString,
  workspace_slug: looseString,
  effectivePermissionsSummary: z
    .object({
      globalActions: looseStringArray,
      projectScopeCount: numberLike
    })
    .optional()
});
export type MeResponseDto = z.infer<typeof meResponseDtoSchema>;

export const workspaceSettingsResponseDtoSchema = z.object({
  settings: z
    .object({
      defaultWorkspaceRole: looseString,
      defaultProjectRole: looseString,
      // Plain truthy coercion (`Boolean(x)`), matching the original
      // `Boolean(dto.settings?.referencingEnabled)` -- not a strict
      // typeof-boolean check.
      referencingEnabled: z.unknown().transform((value) => Boolean(value))
    })
    .optional()
});
export type WorkspaceSettingsResponseDto = z.infer<typeof workspaceSettingsResponseDtoSchema>;

export const workspaceMemberDtoSchema = z.object({
  username: looseString,
  email: looseString,
  fullName: looseString,
  full_name: looseString,
  workspaceRole: looseString,
  workspace_role: looseString,
  disabled: z.unknown().transform((value) => Boolean(value)),
  createdAt: looseString,
  created_at: looseString
});
export type WorkspaceMemberDto = z.infer<typeof workspaceMemberDtoSchema>;

export const workspaceGroupDtoSchema = z.object({
  id: looseString,
  _id: looseString,
  slug: looseString,
  name: looseString,
  description: looseString,
  createdAt: looseString,
  created_at: looseString
});
export type WorkspaceGroupDto = z.infer<typeof workspaceGroupDtoSchema>;

export const workspaceGroupMappingDtoSchema = z.object({
  id: looseString,
  _id: looseString,
  provider: looseString,
  externalGroupKey: looseString,
  external_group_key: looseString,
  groupSlug: looseString,
  group_slug: looseString,
  createdAt: looseString,
  created_at: looseString
});
export type WorkspaceGroupMappingDto = z.infer<typeof workspaceGroupMappingDtoSchema>;

export const workspaceProjectMemberDtoSchema = z.object({
  subjectType: looseString,
  subject_type: looseString,
  subjectId: looseString,
  subject_id: looseString,
  role: looseString,
  groupSlug: looseString,
  group_slug: looseString
});
export type WorkspaceProjectMemberDto = z.infer<typeof workspaceProjectMemberDtoSchema>;
