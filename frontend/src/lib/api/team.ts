import { apiClient } from './client';
import {
  mapWorkspaceMemberDto,
  mapWorkspaceProjectMemberDto,
  mapWorkspaceSettingsResponseDto
} from './mappers';
import type {
  WorkspaceMember,
  WorkspaceMembersResponseDto,
  WorkspaceProjectMember,
  WorkspaceProjectMembersResponseDto,
  WorkspaceSettings,
  WorkspaceSettingsResponseDto
} from './types';

export async function getWorkspaceSettings(): Promise<WorkspaceSettings> {
  const response = await apiClient<WorkspaceSettingsResponseDto>('/workspace/settings');
  return mapWorkspaceSettingsResponseDto(response);
}

export async function updateWorkspaceSettings(
  updates: Partial<{
    defaultWorkspaceRole: WorkspaceSettings['defaultWorkspaceRole'];
    defaultProjectRole: WorkspaceSettings['defaultProjectRole'];
    referencingEnabled: boolean;
  }>
): Promise<WorkspaceSettings> {
  const response = await apiClient<WorkspaceSettingsResponseDto>('/workspace/settings', {
    method: 'PATCH',
    body: JSON.stringify(updates)
  });
  return mapWorkspaceSettingsResponseDto(response);
}

export async function getWorkspaceMembers(): Promise<WorkspaceMember[]> {
  const response = await apiClient<WorkspaceMembersResponseDto>('/workspace/members');
  return (response.members ?? []).map(mapWorkspaceMemberDto);
}

export async function createWorkspaceMember(input: {
  username: string;
  password: string;
  email?: string;
  fullName?: string;
  workspaceRole?: WorkspaceMember['workspaceRole'];
}) {
  await apiClient<WorkspaceMembersResponseDto>('/workspace/members', {
    method: 'POST',
    body: JSON.stringify(input)
  });
}

export async function updateWorkspaceMember(
  username: string,
  updates: Partial<{
    email: string;
    fullName: string;
    workspaceRole: WorkspaceMember['workspaceRole'];
    disabled: boolean;
  }>
) {
  await apiClient<WorkspaceMembersResponseDto>(`/workspace/members/${username}`, {
    method: 'PATCH',
    body: JSON.stringify(updates)
  });
}

export async function disableWorkspaceMember(username: string) {
  await apiClient<WorkspaceMembersResponseDto>(`/workspace/members/${username}`, {
    method: 'DELETE'
  });
}

export async function getProjectMembers(projectSlug: string): Promise<WorkspaceProjectMember[]> {
  const response = await apiClient<WorkspaceProjectMembersResponseDto>(
    `/workspace/projects/${projectSlug}/members`
  );
  return (response.members ?? []).map(mapWorkspaceProjectMemberDto);
}

export async function setProjectMember(input: {
  projectSlug: string;
  subjectType: WorkspaceProjectMember['subjectType'];
  subjectId: string;
  role: WorkspaceProjectMember['role'];
}) {
  await apiClient<{ status?: string }>(`/workspace/projects/${input.projectSlug}/members`, {
    method: 'PUT',
    body: JSON.stringify({
      subjectType: input.subjectType,
      subjectId: input.subjectId,
      role: input.role
    })
  });
}

export async function removeProjectMember(input: {
  projectSlug: string;
  subjectType: WorkspaceProjectMember['subjectType'];
  subjectId: string;
}) {
  await apiClient<{ status?: string }>(
    `/workspace/projects/${input.projectSlug}/members/${input.subjectType}/${input.subjectId}`,
    {
      method: 'DELETE'
    }
  );
}
