const DEFAULT_API_BASE_URL = '/api';
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(/\/+$/, '');

type ParseAs = 'json' | 'text' | 'auto';

interface ApiClientOptions extends RequestInit {
  parseAs?: ParseAs;
}

export class ApiClientError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = 'ApiClientError';
    this.status = status;
    this.body = body;
  }
}

function buildUrl(endpoint: string): string {
  if (endpoint.startsWith('http://') || endpoint.startsWith('https://')) {
    return endpoint;
  }
  const normalizedEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  return `${API_BASE_URL}${normalizedEndpoint}`;
}

function buildHeaders(options: ApiClientOptions, token: string | null): Headers {
  const headers = new Headers(options.headers);

  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const hasBody = options.body !== undefined && options.body !== null;
  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;
  if (hasBody && !isFormData && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  return headers;
}

async function parseErrorBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) {
    return response.json().catch(() => null);
  }
  return response.text().catch(() => null);
}

function toErrorMessage(body: unknown, fallbackStatus: number): string {
  if (typeof body === 'string' && body.trim()) {
    return body;
  }

  if (body && typeof body === 'object') {
    const maybeMessage = (body as { message?: unknown; error?: unknown }).message ??
      (body as { message?: unknown; error?: unknown }).error;
    if (typeof maybeMessage === 'string' && maybeMessage.trim()) {
      return maybeMessage;
    }
  }

  return `API Error: ${fallbackStatus}`;
}

async function parseSuccessBody<T>(response: Response, parseAs: ParseAs): Promise<T> {
  if (response.status === 204) {
    return undefined as T;
  }

  if (parseAs === 'text') {
    return (await response.text()) as T;
  }

  if (parseAs === 'auto') {
    const contentType = response.headers.get('content-type') ?? '';
    if (!contentType.includes('application/json')) {
      return (await response.text()) as T;
    }
  }

  return response.json() as Promise<T>;
}

export async function apiClient<T>(endpoint: string, options: ApiClientOptions = {}): Promise<T> {
  const token = localStorage.getItem('ssm_token');
  const response = await fetch(buildUrl(endpoint), {
    ...options,
    headers: buildHeaders(options, token)
  });

  if (!response.ok) {
    if (response.status === 401 && window.location.pathname !== '/login') {
      localStorage.removeItem('ssm_token');
      window.location.href = '/login';
    }

    const errorBody = await parseErrorBody(response);
    throw new ApiClientError(toErrorMessage(errorBody, response.status), response.status, errorBody);
  }

  return parseSuccessBody<T>(response, options.parseAs ?? 'json');
}

export function apiClientText(endpoint: string, options: Omit<ApiClientOptions, 'parseAs'> = {}) {
  return apiClient<string>(endpoint, {
    ...options,
    parseAs: 'text'
  });
}

export const apiFetch = apiClient;
