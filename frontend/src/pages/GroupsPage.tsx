import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select';
import {
  createWorkspaceGroup,
  createWorkspaceGroupMapping,
  deleteWorkspaceGroup,
  deleteWorkspaceGroupMapping,
  getWorkspaceGroupMappings,
  getWorkspaceGroupMembers,
  getWorkspaceGroups,
  setWorkspaceGroupMembers
} from '../lib/api/groups';
import { getProjects } from '../lib/api/projects';
import { getProjectMembers, removeProjectMember, setProjectMember } from '../lib/api/team';
import { getMe } from '../lib/api/me';
import { queryKeys } from '../lib/api/queryKeys';
import type { WorkspaceProjectMember } from '../lib/api/types';
import { notifyApiError } from '../lib/api/errorToast';

const PROJECT_ROLES: WorkspaceProjectMember['role'][] = ['admin', 'collaborator', 'viewer', 'none'];

export function GroupsPage() {
  const queryClient = useQueryClient();
  const { data: me } = useQuery({ queryKey: queryKeys.me(), queryFn: getMe });
  const canManage = me?.workspaceRole === 'owner' || me?.workspaceRole === 'admin';

  const { data: groups = [] } = useQuery({
    queryKey: queryKeys.workspaceGroups(),
    queryFn: getWorkspaceGroups
  });

  const { data: mappings = [] } = useQuery({
    queryKey: queryKeys.workspaceMappings(),
    queryFn: getWorkspaceGroupMappings
  });

  const { data: projects = [] } = useQuery({
    queryKey: queryKeys.projects(),
    queryFn: getProjects
  });

  const [selectedGroupSlug, setSelectedGroupSlug] = useState<string>('');
  useEffect(() => {
    if (!selectedGroupSlug && groups.length > 0) {
      setSelectedGroupSlug(groups[0].slug);
    }
    if (selectedGroupSlug && !groups.some((group) => group.slug === selectedGroupSlug)) {
      setSelectedGroupSlug(groups[0]?.slug ?? '');
    }
  }, [groups, selectedGroupSlug]);

  const selectedGroup = useMemo(
    () => groups.find((group) => group.slug === selectedGroupSlug) ?? null,
    [groups, selectedGroupSlug]
  );

  const [newGroupSlug, setNewGroupSlug] = useState('');
  const [newGroupName, setNewGroupName] = useState('');

  const [memberToAdd, setMemberToAdd] = useState('');
  const [memberToRemove, setMemberToRemove] = useState('');

  const [projectSlug, setProjectSlug] = useState('');
  const [projectRole, setProjectRole] = useState<WorkspaceProjectMember['role']>('viewer');

  useEffect(() => {
    if (!projectSlug && projects.length > 0) {
      setProjectSlug(projects[0].slug);
    }
  }, [projects, projectSlug]);

  const { data: groupMembers = [] } = useQuery({
    queryKey: queryKeys.workspaceGroupMembers(selectedGroupSlug),
    queryFn: () => getWorkspaceGroupMembers(selectedGroupSlug),
    enabled: Boolean(selectedGroupSlug)
  });

  const { data: selectedProjectMembers = [] } = useQuery({
    queryKey: queryKeys.workspaceProjectMembers(projectSlug),
    queryFn: () => getProjectMembers(projectSlug),
    enabled: Boolean(projectSlug)
  });

  const currentGroupProjectRole = useMemo(() => {
    if (!selectedGroupSlug) return null;
    const match = selectedProjectMembers.find((item) => item.subjectType === 'group' && item.groupSlug === selectedGroupSlug);
    return match?.role ?? null;
  }, [selectedProjectMembers, selectedGroupSlug]);

  const createGroupMutation = useMutation({
    mutationFn: createWorkspaceGroup,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workspaceGroups() });
      setNewGroupSlug('');
      setNewGroupName('');
      toast.success('Group created');
    },
    onError: (error) => notifyApiError(error, 'Failed to create group')
  });

  const deleteGroupMutation = useMutation({
    mutationFn: deleteWorkspaceGroup,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workspaceGroups() });
      queryClient.invalidateQueries({ queryKey: queryKeys.workspaceGroupMembers(selectedGroupSlug) });
      toast.success('Group deleted');
    },
    onError: (error) => notifyApiError(error, 'Failed to delete group')
  });

  const setMembersMutation = useMutation({
    mutationFn: ({ add, remove }: { add?: string[]; remove?: string[] }) =>
      setWorkspaceGroupMembers(selectedGroupSlug, { add, remove }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workspaceGroupMembers(selectedGroupSlug) });
      setMemberToAdd('');
      setMemberToRemove('');
      toast.success('Group members updated');
    },
    onError: (error) => notifyApiError(error, 'Failed to update group members')
  });

  const createMappingMutation = useMutation({
    mutationFn: createWorkspaceGroupMapping,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workspaceMappings() });
      toast.success('Mapping created');
    },
    onError: (error) => notifyApiError(error, 'Failed to create mapping')
  });

  const deleteMappingMutation = useMutation({
    mutationFn: deleteWorkspaceGroupMapping,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workspaceMappings() });
      toast.success('Mapping deleted');
    },
    onError: (error) => notifyApiError(error, 'Failed to delete mapping')
  });

  const setProjectRoleMutation = useMutation({
    mutationFn: setProjectMember,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workspaceProjectMembers(projectSlug) });
      toast.success('Project role updated');
    },
    onError: (error) => notifyApiError(error, 'Failed to set project role')
  });

  const removeProjectRoleMutation = useMutation({
    mutationFn: removeProjectMember,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workspaceProjectMembers(projectSlug) });
      toast.success('Project assignment removed');
    },
    onError: (error) => notifyApiError(error, 'Failed to remove project assignment')
  });

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-lg font-semibold">Groups</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card>
          <CardHeader>
            <CardTitle>Groups</CardTitle>
            <CardDescription>Create and select groups.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {groups.map((group) => (
              <div
                key={group.slug}
                className={`border rounded-md p-2 cursor-pointer ${selectedGroupSlug === group.slug ? 'border-primary' : ''}`}
                onClick={() => setSelectedGroupSlug(group.slug)}
              >
                <p className="text-sm font-medium">{group.name}</p>
                <p className="text-xs text-muted-foreground">{group.slug}</p>
              </div>
            ))}

            {canManage && (
              <>
                <Input
                  placeholder="Group slug"
                  value={newGroupSlug}
                  onChange={(event) => setNewGroupSlug(event.target.value)}
                />
                <Input
                  placeholder="Group name"
                  value={newGroupName}
                  onChange={(event) => setNewGroupName(event.target.value)}
                />
                <Button
                  className="w-full"
                  disabled={!newGroupSlug.trim() || createGroupMutation.isPending}
                  onClick={() =>
                    createGroupMutation.mutate({
                      slug: newGroupSlug.trim(),
                      name: newGroupName.trim() || undefined
                    })
                  }
                >
                  Create Group
                </Button>
                {selectedGroup && (
                  <Button
                    variant="outline"
                    className="w-full"
                    disabled={deleteGroupMutation.isPending}
                    onClick={() => deleteGroupMutation.mutate(selectedGroup.slug)}
                  >
                    Delete Selected Group
                  </Button>
                )}
              </>
            )}
          </CardContent>
        </Card>

        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Group Members</CardTitle>
              <CardDescription>{selectedGroup ? selectedGroup.slug : 'Select a group'}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap gap-2">
                {groupMembers.map((username) => (
                  <span key={username} className="text-xs px-2 py-1 rounded-md bg-muted">
                    {username}
                  </span>
                ))}
              </div>

              {canManage && selectedGroup && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                  <Input
                    placeholder="Username to add"
                    value={memberToAdd}
                    onChange={(event) => setMemberToAdd(event.target.value)}
                  />
                  <Input
                    placeholder="Username to remove"
                    value={memberToRemove}
                    onChange={(event) => setMemberToRemove(event.target.value)}
                  />
                  <Button
                    disabled={setMembersMutation.isPending || (!memberToAdd.trim() && !memberToRemove.trim())}
                    onClick={() =>
                      setMembersMutation.mutate({
                        add: memberToAdd.trim() ? [memberToAdd.trim()] : [],
                        remove: memberToRemove.trim() ? [memberToRemove.trim()] : []
                      })
                    }
                  >
                    Apply Member Changes
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Project Access</CardTitle>
              <CardDescription>Assign selected group to a project role.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                <Select value={projectSlug} onValueChange={setProjectSlug}>
                  <SelectTrigger>
                    <SelectValue placeholder="Project" />
                  </SelectTrigger>
                  <SelectContent>
                    {projects.map((project) => (
                      <SelectItem key={project.slug} value={project.slug}>
                        {project.slug}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select value={projectRole} onValueChange={(value) => setProjectRole(value as WorkspaceProjectMember['role'])}>
                  <SelectTrigger>
                    <SelectValue placeholder="Role" />
                  </SelectTrigger>
                  <SelectContent>
                    {PROJECT_ROLES.map((role) => (
                      <SelectItem key={role} value={role}>
                        {role}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  disabled={!canManage || !selectedGroup || !projectSlug || setProjectRoleMutation.isPending}
                  onClick={() =>
                    selectedGroup &&
                    setProjectRoleMutation.mutate({
                      projectSlug,
                      subjectType: 'group',
                      subjectId: selectedGroup.slug,
                      role: projectRole
                    })
                  }
                >
                  Set Role
                </Button>
              </div>

              <div className="border rounded-md p-3 flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">Current assignment</p>
                  <p className="text-xs text-muted-foreground">
                    {selectedGroup && projectSlug
                      ? `${selectedGroup.slug} in ${projectSlug}: ${currentGroupProjectRole ?? 'none'}`
                      : 'Select group and project'}
                  </p>
                </div>
                <Button
                  variant="outline"
                  disabled={!canManage || !selectedGroup || !projectSlug || !currentGroupProjectRole}
                  onClick={() =>
                    selectedGroup &&
                    removeProjectRoleMutation.mutate({
                      projectSlug,
                      subjectType: 'group',
                      subjectId: selectedGroup.slug
                    })
                  }
                >
                  Remove Assignment
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Group Mappings</CardTitle>
              <CardDescription>Map external keys to workspace groups.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {mappings.map((mapping) => (
                <div key={mapping.id} className="border rounded-md p-3 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium">{mapping.externalGroupKey}</p>
                    <p className="text-xs text-muted-foreground">
                      {mapping.provider} → {mapping.groupSlug ?? 'unknown'}
                    </p>
                  </div>
                  {canManage && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => deleteMappingMutation.mutate(mapping.id)}
                    >
                      Delete
                    </Button>
                  )}
                </div>
              ))}

              {canManage && selectedGroup && (
                <Button
                  variant="outline"
                  onClick={() =>
                    createMappingMutation.mutate({
                      provider: 'manual',
                      externalGroupKey: selectedGroup.slug,
                      groupSlug: selectedGroup.slug
                    })
                  }
                >
                  Create Mapping for Selected Group
                </Button>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
