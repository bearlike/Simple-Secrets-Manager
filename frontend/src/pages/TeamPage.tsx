import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select';
import {
  createWorkspaceMember,
  getWorkspaceMembers,
  getWorkspaceSettings,
  updateWorkspaceMember,
  updateWorkspaceSettings
} from '../lib/api/team';
import { getMe } from '../lib/api/me';
import { queryKeys } from '../lib/api/queryKeys';
import type { WorkspaceMember, WorkspaceSettings } from '../lib/api/types';
import { notifyApiError } from '../lib/api/errorToast';

const WORKSPACE_ROLES: WorkspaceMember['workspaceRole'][] = ['owner', 'admin', 'collaborator', 'viewer'];
const PROJECT_ROLES: WorkspaceSettings['defaultProjectRole'][] = ['admin', 'collaborator', 'viewer', 'none'];

export function TeamPage() {
  const queryClient = useQueryClient();
  const { data: me } = useQuery({ queryKey: queryKeys.me(), queryFn: getMe });
  const canViewSettings = me?.workspaceRole === 'owner' || me?.workspaceRole === 'admin';
  const { data: members = [], isLoading: membersLoading } = useQuery({
    queryKey: queryKeys.workspaceMembers(),
    queryFn: getWorkspaceMembers
  });
  const { data: settings } = useQuery({
    queryKey: queryKeys.workspaceSettings(),
    queryFn: getWorkspaceSettings,
    enabled: canViewSettings
  });

  const canManageMembers = me?.workspaceRole === 'owner';
  const canManageSettings = me?.workspaceRole === 'owner';

  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRole, setNewRole] = useState<WorkspaceMember['workspaceRole']>('viewer');

  const addMemberMutation = useMutation({
    mutationFn: createWorkspaceMember,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workspaceMembers() });
      setNewUsername('');
      setNewPassword('');
      setNewRole('viewer');
      toast.success('Member added');
    },
    onError: (error) => notifyApiError(error, 'Failed to add member')
  });

  const updateMemberMutation = useMutation({
    mutationFn: ({ username, updates }: { username: string; updates: Parameters<typeof updateWorkspaceMember>[1] }) =>
      updateWorkspaceMember(username, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workspaceMembers() });
    },
    onError: (error) => notifyApiError(error, 'Failed to update member')
  });

  const setMemberStatusMutation = useMutation({
    mutationFn: ({ username, disabled }: { username: string; disabled: boolean }) =>
      updateWorkspaceMember(username, { disabled }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workspaceMembers() });
      toast.success('Member status updated');
    },
    onError: (error) => notifyApiError(error, 'Failed to update member status')
  });

  const updateSettingsMutation = useMutation({
    mutationFn: updateWorkspaceSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workspaceSettings() });
      toast.success('Workspace settings updated');
    },
    onError: (error) => notifyApiError(error, 'Failed to update settings')
  });

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-lg font-semibold">Team</h1>

      <Tabs defaultValue="members" className="space-y-4">
        <TabsList>
          <TabsTrigger value="members">Members</TabsTrigger>
          {canViewSettings && <TabsTrigger value="defaults">Roles & Defaults</TabsTrigger>}
        </TabsList>

        <TabsContent value="members">
          <Card>
            <CardHeader>
              <CardTitle>Workspace Members</CardTitle>
              <CardDescription>Manage users and workspace roles.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {canManageMembers && (
                <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                  <Input
                    placeholder="Username"
                    value={newUsername}
                    onChange={(event) => setNewUsername(event.target.value)}
                  />
                  <Input
                    placeholder="Password"
                    type="password"
                    value={newPassword}
                    onChange={(event) => setNewPassword(event.target.value)}
                  />
                  <Select value={newRole} onValueChange={(value) => setNewRole(value as WorkspaceMember['workspaceRole'])}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {WORKSPACE_ROLES.map((role) => (
                        <SelectItem key={role} value={role}>
                          {role}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button
                    disabled={addMemberMutation.isPending || !newUsername.trim() || !newPassword}
                    onClick={() =>
                      addMemberMutation.mutate({
                        username: newUsername.trim(),
                        password: newPassword,
                        workspaceRole: newRole
                      })
                    }
                  >
                    Add Member
                  </Button>
                </div>
              )}

              {membersLoading ? (
                <p className="text-sm text-muted-foreground">Loading members...</p>
              ) : (
                <div className="space-y-2">
                  {members.map((member) => (
                    <div
                      key={member.username}
                      className="border rounded-md p-3 flex flex-col md:flex-row md:items-center gap-3"
                    >
                      <div className="min-w-40">
                        <p className="text-sm font-medium">{member.username}</p>
                        <p className="text-xs text-muted-foreground">{member.email ?? 'No email'}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Select
                          value={member.workspaceRole}
                          disabled={!canManageMembers || member.username === me?.username}
                          onValueChange={(value) =>
                            updateMemberMutation.mutate({
                              username: member.username,
                              updates: { workspaceRole: value as WorkspaceMember['workspaceRole'] }
                            })
                          }
                        >
                          <SelectTrigger className="w-40">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {WORKSPACE_ROLES.map((role) => (
                              <SelectItem key={role} value={role}>
                                {role}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <Button
                          variant="outline"
                          role="switch"
                          aria-checked={!member.disabled}
                          disabled={!canManageMembers || member.username === me?.username}
                          onClick={() =>
                            setMemberStatusMutation.mutate({
                              username: member.username,
                              disabled: !member.disabled
                            })
                          }
                        >
                          {member.disabled ? 'Disabled (click to enable)' : 'Enabled (click to disable)'}
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {canViewSettings && <TabsContent value="defaults">
          <Card>
            <CardHeader>
              <CardTitle>Workspace Defaults</CardTitle>
              <CardDescription>Default roles and feature toggles.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {!settings ? (
                <p className="text-sm text-muted-foreground">Loading settings...</p>
              ) : (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <p className="text-xs text-muted-foreground">Default Workspace Role</p>
                      <Select
                        value={settings.defaultWorkspaceRole}
                        disabled={!canManageSettings}
                        onValueChange={(value) =>
                          updateSettingsMutation.mutate({
                            defaultWorkspaceRole: value as WorkspaceSettings['defaultWorkspaceRole']
                          })
                        }
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {WORKSPACE_ROLES.map((role) => (
                            <SelectItem key={role} value={role}>
                              {role}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <p className="text-xs text-muted-foreground">Default Project Role</p>
                      <Select
                        value={settings.defaultProjectRole}
                        disabled={!canManageSettings}
                        onValueChange={(value) =>
                          updateSettingsMutation.mutate({
                            defaultProjectRole: value as WorkspaceSettings['defaultProjectRole']
                          })
                        }
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {PROJECT_ROLES.map((role) => (
                            <SelectItem key={role} value={role}>
                              {role}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <div className="flex items-center justify-between border rounded-md p-3">
                    <div>
                      <p className="text-sm font-medium">Secret Referencing</p>
                      <p className="text-xs text-muted-foreground">Allow ${'{...}'} placeholders to resolve.</p>
                    </div>
                    <Button
                      variant="outline"
                      disabled={!canManageSettings}
                      onClick={() =>
                        updateSettingsMutation.mutate({
                          referencingEnabled: !settings.referencingEnabled
                        })
                      }
                    >
                      {settings.referencingEnabled ? 'Enabled' : 'Disabled'}
                    </Button>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>}
      </Tabs>
    </div>
  );
}
