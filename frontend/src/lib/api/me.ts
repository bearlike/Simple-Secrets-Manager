import { apiClient } from './client';
import { mapMeResponseDto } from './mappers';
import { meResponseDtoSchema } from './schemas';
import type { MeProfile } from './types';

export async function getMe(): Promise<MeProfile> {
  const response = await apiClient<unknown>('/me');
  return mapMeResponseDto(meResponseDtoSchema.parse(response));
}

export async function updateMe(input: { email?: string; fullName?: string }): Promise<MeProfile> {
  const response = await apiClient<unknown>('/me', {
    method: 'PATCH',
    body: JSON.stringify(input)
  });
  return mapMeResponseDto(meResponseDtoSchema.parse(response));
}
