import { apiClient } from './client';

interface LoginResponseDto {
  token?: string;
}

interface LoginInput {
  username: string;
  password: string;
}

function asString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim().length > 0 ? value : undefined;
}

function encodeBasicAuth(username: string, password: string): string {
  const raw = `${username}:${password}`;
  const bytes = new TextEncoder().encode(raw);
  let binary = '';
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary);
}

export async function loginWithUserpass({ username, password }: LoginInput): Promise<string> {
  const response = await apiClient<LoginResponseDto>('/auth/tokens/', {
    method: 'GET',
    headers: {
      Authorization: `Basic ${encodeBasicAuth(username, password)}`
    }
  });

  const token = asString(response.token);
  if (!token) {
    throw new Error('Login succeeded but token was not returned');
  }
  return token;
}
