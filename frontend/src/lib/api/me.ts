import { apiClient } from './client';
import { mapMeResponseDto } from './mappers';
import type { MeProfile, MeResponseDto } from './types';

export async function getMe(): Promise<MeProfile> {
  const response = await apiClient<MeResponseDto>('/me');
  return mapMeResponseDto(response);
}

export async function updateMe(input: { email?: string; fullName?: string }): Promise<MeProfile> {
  const response = await apiClient<MeResponseDto>('/me', {
    method: 'PATCH',
    body: JSON.stringify(input)
  });
  return mapMeResponseDto(response);
}
