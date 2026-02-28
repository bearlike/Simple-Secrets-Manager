import { apiClient } from './client';
import {
  mapWorkspaceGroupDto,
  mapWorkspaceGroupMappingDto
} from './mappers';
import type {
  WorkspaceGroup,
  WorkspaceGroupMappingsResponseDto,
  WorkspaceGroupMembersResponseDto,
  WorkspaceGroupMapping,
  WorkspaceGroupsResponseDto
} from './types';

export async function getWorkspaceGroups(): Promise<WorkspaceGroup[]> {
  const response = await apiClient<WorkspaceGroupsResponseDto>('/workspace/groups');
  return (response.groups ?? []).map(mapWorkspaceGroupDto);
}

export async function createWorkspaceGroup(input: { slug: string; name?: string; description?: string }) {
  await apiClient<WorkspaceGroupsResponseDto>('/workspace/groups', {
    method: 'POST',
    body: JSON.stringify(input)
  });
}

export async function updateWorkspaceGroup(
  groupSlug: string,
  input: Partial<{ name: string; description: string }>
) {
  await apiClient<WorkspaceGroupsResponseDto>(`/workspace/groups/${groupSlug}`, {
    method: 'PATCH',
    body: JSON.stringify(input)
  });
}

export async function deleteWorkspaceGroup(groupSlug: string) {
  await apiClient<{ status?: string }>(`/workspace/groups/${groupSlug}`, {
    method: 'DELETE'
  });
}

export async function getWorkspaceGroupMembers(groupSlug: string): Promise<string[]> {
  const response = await apiClient<WorkspaceGroupMembersResponseDto>(`/workspace/groups/${groupSlug}/members`);
  return (response.members ?? []).filter((value): value is string => typeof value === 'string');
}

export async function setWorkspaceGroupMembers(
  groupSlug: string,
  input: {
    add?: string[];
    remove?: string[];
  }
): Promise<string[]> {
  const response = await apiClient<WorkspaceGroupMembersResponseDto>(
    `/workspace/groups/${groupSlug}/members`,
    {
      method: 'PUT',
      body: JSON.stringify({ add: input.add ?? [], remove: input.remove ?? [] })
    }
  );
  return (response.members ?? []).filter((value): value is string => typeof value === 'string');
}

export async function getWorkspaceGroupMappings(): Promise<WorkspaceGroupMapping[]> {
  const response = await apiClient<WorkspaceGroupMappingsResponseDto>('/workspace/group-mappings');
  return (response.mappings ?? []).map(mapWorkspaceGroupMappingDto);
}

export async function createWorkspaceGroupMapping(input: {
  provider?: string;
  externalGroupKey: string;
  groupSlug: string;
}) {
  await apiClient<WorkspaceGroupMappingsResponseDto>('/workspace/group-mappings', {
    method: 'POST',
    body: JSON.stringify({
      provider: input.provider ?? 'manual',
      externalGroupKey: input.externalGroupKey,
      groupSlug: input.groupSlug
    })
  });
}

export async function deleteWorkspaceGroupMapping(mappingId: string) {
  await apiClient<{ status?: string }>(`/workspace/group-mappings/${mappingId}`, {
    method: 'DELETE'
  });
}
