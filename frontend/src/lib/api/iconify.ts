import { z } from 'zod';
import { looseString, looseStringArray, parseRecordSafely } from './schemas';

// Client for the public Iconify API (https://iconify.design/docs/api/).
// This is the same service `AppIcon` already renders every icon from, so the
// picker's search/browse adds no new external dependency in practice. It is
// deliberately NOT routed through `apiClient`: different origin, no auth
// header, no `{"message": ...}` error envelope. Schemas are colocated here
// (not in `schemas.ts`, which documents OUR API's wire shapes).
const ICONIFY_API_BASE = 'https://api.iconify.design';

// API maximum. Results are relevance-ranked, so a hit past 999 means the
// query needs narrowing anyway.
const SEARCH_LIMIT = 999;

export interface IconCollection {
  prefix: string;
  name: string;
  total: number;
}

const collectionInfoSchema = z.object({
  name: looseString,
  total: z.unknown().transform((value) => (typeof value === 'number' ? value : 0))
});

// /collection returns names split into `uncategorized` and/or per-category
// lists depending on the pack; flatten both into one list here so consumers
// never see that split.
const packContentsSchema = z.object({
  uncategorized: looseStringArray,
  categories: z.unknown().transform((value): string[] => {
    if (!value || typeof value !== 'object') {
      return [];
    }
    return Object.values(value as Record<string, unknown>).flatMap((names) =>
      looseStringArray.parse(names)
    );
  })
});

const searchResponseSchema = z.object({
  icons: looseStringArray
});

async function iconifyGet(path: string): Promise<unknown> {
  const response = await fetch(`${ICONIFY_API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`Iconify API error: ${response.status}`);
  }
  return response.json();
}

// Param-less: safe to pass directly as a TanStack `queryFn` (see
// frontend/AGENTS.md -- a queryFn must not take an optional-object param).
export async function getIconCollections(): Promise<IconCollection[]> {
  const payload = await iconifyGet('/collections');
  const record = parseRecordSafely(collectionInfoSchema, payload);
  return Object.entries(record)
    .map(([prefix, info]) => ({ prefix, name: info.name ?? prefix, total: info.total }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

// Takes params, so at useQuery call sites these MUST be arrow-wrapped.
export async function getCollectionIcons(prefix: string): Promise<string[]> {
  const payload = await iconifyGet(`/collection?prefix=${encodeURIComponent(prefix)}`);
  const parsed = packContentsSchema.parse(payload);
  return [...new Set([...parsed.uncategorized, ...parsed.categories])];
}

export async function searchIcons(query: string, prefix?: string): Promise<string[]> {
  const params = new URLSearchParams({ query, limit: String(SEARCH_LIMIT) });
  if (prefix) {
    params.set('prefix', prefix);
  }
  const payload = await iconifyGet(`/search?${params.toString()}`);
  return searchResponseSchema.parse(payload).icons;
}
