import { useEffect, useState } from 'react';
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
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { IconSlugPicker } from './IconSlugPicker';
import { ApiClientError } from '../../lib/api/client';
import { updateSecret } from '../../lib/api/secrets';
import { queryKeys } from '../../lib/api/queryKeys';
import type { Secret } from '../../lib/api/types';
import { SecretValueEditor } from './SecretValueEditor';
import { useReferenceSuggestions } from './useReferenceSuggestions';
import { ConfirmDialog } from '../common/ConfirmDialog';
import {
  normalizeSecretValueForSubmit,
  requiresEmptyValueConfirmation
} from './secretValueSubmit';

const schema = z.object({
  value: z.string(),
  sensitive: z.boolean(),
  iconSlug: z
    .string()
    .optional()
    .transform((value) => value?.trim().toLowerCase() ?? '')
    .refine((value) => value.length === 0 || /^[a-z0-9-]+:[a-z0-9][a-z0-9-]*$/.test(value), {
      message: 'Icon slug must match "prefix:name"'
    }),
  description: z.string().optional()
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
  const [pendingSubmit, setPendingSubmit] = useState<FormValues | null>(null);
  const {
    control,
    handleSubmit,
    reset,
    formState: { errors }
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      value: secret?.value ?? '',
      sensitive: secret?.sensitive ?? true,
      iconSlug: secret?.iconSlug ?? '',
      description: secret?.description ?? ''
    }
  });

  useEffect(() => {
    reset({
      value: secret?.value ?? '',
      sensitive: secret?.sensitive ?? true,
      iconSlug: secret?.iconSlug ?? '',
      description: secret?.description ?? ''
    });
  }, [secret?.key, secret?.value, secret?.sensitive, secret?.iconSlug, secret?.description, reset]);

  const mutation = useMutation({
    mutationFn: (data: FormValues) => {
      if (!secret) throw new Error('No secret selected');
      return updateSecret(projectSlug, configSlug, secret.key, {
        value: data.value,
        iconSlug: data.iconSlug || null,
        sensitive: data.sensitive,
        description: data.description?.trim() || null
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.secrets(projectSlug, configSlug)
      });
      toast.success('Secret updated');
      setPendingSubmit(null);
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

  const submitValue = (data: FormValues) => mutation.mutate(data);
  const onSubmit = (data: FormValues) => {
    const normalizedValue = normalizeSecretValueForSubmit(data.value);
    const normalized = {
      ...data,
      value: normalizedValue
    };
    if (requiresEmptyValueConfirmation(data.value)) {
      setPendingSubmit(normalized);
      return;
    }
    submitValue(normalized);
  };

  return (
    <>
      <Dialog
        open={open}
        onOpenChange={(next) => {
          onOpenChange(next);
          if (!next) {
            mutation.reset();
            setPendingSubmit(null);
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
              <Label htmlFor="iconSlug">Icon slug</Label>
              <Controller
                name="iconSlug"
                control={control}
                render={({ field }) => (
                  <IconSlugPicker
                    id="iconSlug"
                    value={field.value ?? ''}
                    onChange={field.onChange}
                    placeholder="simple-icons:sqlalchemy"
                  />
                )}
              />
              {errors.iconSlug && <p className="text-xs text-destructive">{errors.iconSlug.message}</p>}
              <p className="text-xs text-muted-foreground">Clear this field to reset back to auto-detected icon</p>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="secret-edit-description">Description (optional)</Label>
              <Controller
                name="description"
                control={control}
                render={({ field }) => (
                  <Textarea
                    id="secret-edit-description"
                    value={field.value ?? ''}
                    onChange={field.onChange}
                    rows={2}
                    placeholder="What is this secret for?"
                  />
                )}
              />
              <p className="text-xs text-muted-foreground">Optional. A short note about what this secret is for.</p>
            </div>

            <div className="flex items-start justify-between gap-4 rounded-md border border-border px-3 py-2.5">
              <div className="space-y-0.5">
                <Label htmlFor="secret-edit-sensitive">Sensitive</Label>
                <p className="text-xs text-muted-foreground">
                  Masked in tables until revealed. Turn off for non-secret config values.
                </p>
              </div>
              <Controller
                name="sensitive"
                control={control}
                render={({ field }) => (
                  <Switch
                    id="secret-edit-sensitive"
                    checked={field.value}
                    onCheckedChange={field.onChange}
                  />
                )}
              />
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
              <p className="text-xs text-muted-foreground">
                Whitespace-only input is saved as an empty string after confirmation.
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

      <ConfirmDialog
        open={pendingSubmit !== null}
        onOpenChange={(next) => {
          if (!next) setPendingSubmit(null);
        }}
        title="Save Empty Value?"
        description={
          secret ?
            `This will update "${secret.key}" to an empty string value.` :
            'This will update the secret to an empty string value.'
        }
        onConfirm={() => {
          if (!pendingSubmit) return;
          submitValue(pendingSubmit);
        }}
        loading={mutation.isPending}
      />
    </>
  );
}
