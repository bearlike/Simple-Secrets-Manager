import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { PlusIcon } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  getTokens,
  revokeToken,
  isTokenListUnavailableError
} from '../lib/api/tokens';
import { getProjects } from '../lib/api/projects';
import { queryKeys } from '../lib/api/queryKeys';
import { TokensTable } from '../components/tokens/TokensTable';
import { CreateTokenDialog } from '../components/tokens/CreateTokenDialog';

export function TokensPage() {
  const [createOpen, setCreateOpen] = useState(false);
  const [revokingId, setRevokingId] = useState<string | undefined>();
  const queryClient = useQueryClient();

  const tokensQuery = useQuery({
    queryKey: queryKeys.tokens(),
    queryFn: getTokens,
    retry: false
  });

  const { data: projects = [] } = useQuery({
    queryKey: queryKeys.projects(),
    queryFn: getProjects
  });

  const revokeMutation = useMutation({
    mutationFn: (id: string) => revokeToken(id),
    onMutate: (id) => setRevokingId(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tokens() });
      toast.success('Token revoked');
      setRevokingId(undefined);
    },
    onError: () => {
      toast.error('Failed to revoke token');
      setRevokingId(undefined);
    }
  });

  const listUnavailable = isTokenListUnavailableError(tokensQuery.error);
  const hasListError = tokensQuery.isError && !listUnavailable;
  const tokens = listUnavailable ? [] : tokensQuery.data ?? [];

  const serviceTokens = tokens.filter((token) => token.type === 'service');
  const personalTokens = tokens.filter((token) => token.type === 'personal');

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-lg font-semibold">Access Tokens</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Manage API tokens for programmatic access
          </p>
        </div>
        <Button size="sm" className="gap-1.5" onClick={() => setCreateOpen(true)}>
          <PlusIcon className="h-3.5 w-3.5" />
          New Token
        </Button>
      </div>

      {listUnavailable && (
        <Alert className="mb-4">
          <AlertDescription>
            Token listing is not available on this backend yet. You can still create new tokens.
          </AlertDescription>
        </Alert>
      )}

      {hasListError && (
        <Alert className="mb-4 border-red-200 bg-red-50 dark:bg-red-950 dark:border-red-800">
          <AlertDescription className="text-red-700 dark:text-red-300">
            Failed to load tokens. You can still create a new token.
          </AlertDescription>
        </Alert>
      )}

      {!listUnavailable && (
        <Tabs defaultValue="service">
          <TabsList className="mb-4">
            <TabsTrigger value="service">
              Service Tokens
              {serviceTokens.length > 0 && (
                <span className="ml-1.5 text-xs text-muted-foreground">({serviceTokens.length})</span>
              )}
            </TabsTrigger>
            <TabsTrigger value="personal">
              Personal Tokens
              {personalTokens.length > 0 && (
                <span className="ml-1.5 text-xs text-muted-foreground">({personalTokens.length})</span>
              )}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="service">
            <TokensTable
              tokens={serviceTokens}
              onRevoke={(id) => revokeMutation.mutate(id)}
              revoking={revokingId}
              isLoading={tokensQuery.isLoading}
            />
          </TabsContent>

          <TabsContent value="personal">
            <TokensTable
              tokens={personalTokens}
              onRevoke={(id) => revokeMutation.mutate(id)}
              revoking={revokingId}
              isLoading={tokensQuery.isLoading}
            />
          </TabsContent>
        </Tabs>
      )}

      <CreateTokenDialog open={createOpen} onOpenChange={setCreateOpen} projects={projects} />
    </div>
  );
}
