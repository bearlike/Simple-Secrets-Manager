import { useEffect } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { ApiClientError } from '../../lib/api/client';
import { updateSecret } from '../../lib/api/secrets';
import { queryKeys } from '../../lib/api/queryKeys';
import type { Secret } from '../../lib/api/types';
import { SecretValueEditor } from './SecretValueEditor';
import { useReferenceSuggestions } from './useReferenceSuggestions';

const schema = z.object({
  value: z.string().min(1, 'Value is required')
});

type FormValues = z.infer<typeof schema>;

interface EditSecretDialogProps {
  secret: Secret | null;
  projectSlug: string;
  configSlug: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function EditSecretDialog({
  secret,
  projectSlug,
  configSlug,
  open,
  onOpenChange
}: EditSecretDialogProps) {
  const queryClient = useQueryClient();
  const referenceSuggestions = useReferenceSuggestions({ projectSlug, configSlug });
  const {
    control,
    handleSubmit,
    reset,
    formState: { errors }
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      value: secret?.value ?? ''
    }
  });

  useEffect(() => {
    reset({
      value: secret?.value ?? ''
    });
  }, [secret?.key, secret?.value, reset]);

  const mutation = useMutation({
    mutationFn: (data: FormValues) => {
      if (!secret) throw new Error('No secret selected');
      return updateSecret(projectSlug, configSlug, secret.key, data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.secrets(projectSlug, configSlug)
      });
      toast.success('Secret updated');
      onOpenChange(false);
    },
    onError: (error) => {
      if (error instanceof ApiClientError) {
        toast.error(error.message);
        return;
      }
      if (error instanceof Error && error.message.trim()) {
        toast.error(error.message);
        return;
      }
      toast.error('Failed to update secret');
    }
  });

  const onSubmit = (data: FormValues) => mutation.mutate(data);

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        onOpenChange(next);
        if (!next) {
          mutation.reset();
        }
      }}
    >
      <DialogContent className="sm:max-w-[760px]">
        <DialogHeader>
          <DialogTitle>Edit Secret</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 pt-2">
          <div className="space-y-1.5">
            <Label>Key</Label>
            <p className="font-mono text-sm font-medium">{secret?.key ?? '—'}</p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="secret-edit-value">Value</Label>
            <Controller
              name="value"
              control={control}
              render={({ field }) => (
                <SecretValueEditor
                  value={field.value}
                  onChange={field.onChange}
                  rows={12}
                  className="min-h-[320px]"
                  autoFocus
                  autocompleteItems={referenceSuggestions}
                />
              )}
            />

            {errors.value && <p className="text-xs text-destructive">{errors.value.message}</p>}
            <p className="text-xs text-muted-foreground">
              References: <code className="font-mono">${'{KEY}'}</code>,{' '}
              <code className="font-mono">${'{config.KEY}'}</code>,{' '}
              <code className="font-mono">${'{project.config.KEY}'}</code>
            </p>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending || !secret}>
              {mutation.isPending ? 'Saving...' : 'Save'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
