import { ApiClientError, apiClient } from './client';
import { mapAccessToActions, mapTokenDto } from './mappers';
import type {
  CreateTokenInput,
  CreateTokenResponse,
  CreateTokenResponseDto,
  Token,
  TokenDto,
  TokenListResponseDto
} from './types';

const TOKEN_LIST_UNAVAILABLE_STATUSES = new Set([404, 405, 501]);

export class TokenListUnavailableError extends Error {
  constructor(message = 'Token listing is not available on this backend') {
    super(message);
    this.name = 'TokenListUnavailableError';
  }
}

function extractTokenDtos(response: TokenListResponseDto | TokenDto[]): TokenDto[] {
  if (Array.isArray(response)) {
    return response;
  }

  if (Array.isArray(response.tokens)) {
    return response.tokens;
  }

  if (Array.isArray(response.data)) {
    return response.data;
  }

  return [];
}

function asString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value : undefined;
}

function extractPlaintext(response: CreateTokenResponseDto): string {
  const legacyToken = typeof response.token === 'string' ? response.token : undefined;
  return (
    asString(legacyToken) ??
    asString(response.plaintext) ??
    asString(response.token_plaintext) ??
    asString(response.token_value) ??
    asString(response.secret) ??
    ''
  );
}

export async function getTokens(): Promise<Token[]> {
  try {
    const response = await apiClient<TokenListResponseDto | TokenDto[]>('/auth/tokens/v2');
    return extractTokenDtos(response).map(mapTokenDto);
  } catch (error) {
    if (
      error instanceof ApiClientError &&
      TOKEN_LIST_UNAVAILABLE_STATUSES.has(error.status)
    ) {
      throw new TokenListUnavailableError();
    }
    throw error;
  }
}

export async function createToken(data: CreateTokenInput): Promise<CreateTokenResponse> {
  const endpoint =
    data.type === 'service' ? '/auth/tokens/v2/service' : '/auth/tokens/v2/personal';

  const payload: Record<string, unknown> = {
    project: data.projectSlug,
    config: data.configSlug,
    actions: mapAccessToActions(data.access),
    ttl_seconds: data.ttlSeconds
  };

  if (data.type === 'service') {
    payload.service_name = data.serviceName?.trim() || 'service-token';
  }

  const response = await apiClient<CreateTokenResponseDto>(endpoint, {
    method: 'POST',
    body: JSON.stringify(payload)
  });

  const tokenFromResponse = response.token;
  const tokenDto =
    tokenFromResponse && typeof tokenFromResponse === 'object'
      ? tokenFromResponse
      : response.data ?? {
          type: response.type ?? data.type,
          expires_at: response.expires_at
        };

  return {
    token: mapTokenDto(tokenDto),
    plaintext: extractPlaintext(response)
  };
}

export function revokeToken(id: string) {
  return apiClient<void>('/auth/tokens/v2/revoke', {
    method: 'POST',
    body: JSON.stringify({ token_id: id })
  });
}

export function isTokenListUnavailableError(error: unknown): boolean {
  return error instanceof TokenListUnavailableError;
}
