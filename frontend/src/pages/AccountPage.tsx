import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { getMe, updateMe } from '../lib/api/me';
import { queryKeys } from '../lib/api/queryKeys';
import { notifyApiError } from '../lib/api/errorToast';

export function AccountPage() {
  const queryClient = useQueryClient();
  const { data: me, isLoading } = useQuery({
    queryKey: queryKeys.me(),
    queryFn: getMe
  });

  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');

  useEffect(() => {
    if (!me) return;
    setEmail(me.email ?? '');
    setFullName(me.fullName ?? '');
  }, [me]);

  const updateMutation = useMutation({
    mutationFn: updateMe,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.me() });
      toast.success('Profile updated');
    },
    onError: (error) => {
      notifyApiError(error, 'Failed to update profile');
    }
  });

  return (
    <div className="p-6 max-w-3xl">
      <Card>
        <CardHeader>
          <CardTitle>Account</CardTitle>
          <CardDescription>Manage your profile details.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {isLoading || !me ? (
            <p className="text-sm text-muted-foreground">Loading profile...</p>
          ) : (
            <>
              <div className="grid gap-2">
                <label className="text-xs text-muted-foreground">Username</label>
                <Input value={me.username} disabled />
              </div>
              <div className="grid gap-2">
                <label className="text-xs text-muted-foreground">Workspace Role</label>
                <Input value={me.workspaceRole ?? 'unknown'} disabled />
              </div>
              <div className="grid gap-2">
                <label className="text-xs text-muted-foreground">Full Name</label>
                <Input value={fullName} onChange={(event) => setFullName(event.target.value)} />
              </div>
              <div className="grid gap-2">
                <label className="text-xs text-muted-foreground">Email</label>
                <Input value={email} onChange={(event) => setEmail(event.target.value)} />
              </div>
              <div className="flex justify-end">
                <Button
                  disabled={updateMutation.isPending}
                  onClick={() =>
                    updateMutation.mutate({
                      email,
                      fullName
                    })
                  }
                >
                  Save Changes
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
