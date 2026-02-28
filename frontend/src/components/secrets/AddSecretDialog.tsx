import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter } from
'@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ApiClientError } from '../../lib/api/client';
import { createSecret } from '../../lib/api/secrets';
import { queryKeys } from '../../lib/api/queryKeys';
import { SecretValueEditor } from './SecretValueEditor';
import { useReferenceSuggestions } from './useReferenceSuggestions';

const ICON_SLUG_PATTERN = /^[a-z0-9-]+:[a-z0-9][a-z0-9-]*$/;

const schema = z.object({
  key: z.
  string().
  min(1, 'Key is required').
  regex(
    /^[A-Z0-9_]+$/,
    'Key must be uppercase letters, numbers, and underscores only'
  ),
  value: z.string().min(1, 'Value is required'),
  iconSlug: z
    .string()
    .optional()
    .transform((value) => value?.trim().toLowerCase() ?? '')
    .refine((value) => value.length === 0 || ICON_SLUG_PATTERN.test(value), {
      message: 'Icon slug must match "prefix:name"'
    })
});
type FormValues = z.infer<typeof schema>;
interface AddSecretDialogProps {
  projectSlug: string;
  configSlug: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}
export function AddSecretDialog({
  projectSlug,
  configSlug,
  open,
  onOpenChange
}: AddSecretDialogProps) {
  const queryClient = useQueryClient();
  const referenceSuggestions = useReferenceSuggestions({ projectSlug, configSlug });
  const {
    control,
    register,
    handleSubmit,
    reset,
    formState: { errors }
  } = useForm<FormValues>({
    resolver: zodResolver(schema)
  });
  const mutation = useMutation({
    mutationFn: (data: FormValues) =>
    createSecret(projectSlug, configSlug, {
      key: data.key,
      value: data.value,
      iconSlug: data.iconSlug || undefined
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.secrets(projectSlug, configSlug)
      });
      toast.success('Secret created');
      reset();
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
      toast.error('Failed to create secret');
    }
  });
  const onSubmit = (data: FormValues) => mutation.mutate(data);
  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        onOpenChange(v);
        if (!v) reset();
      }}>

      <DialogContent className="sm:max-w-[720px]">
        <DialogHeader>
          <DialogTitle>Add Secret</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 pt-2">
          <div className="space-y-1.5">
            <Label htmlFor="key">Key</Label>
            <Input
              id="key"
              {...register('key')}
              placeholder="DATABASE_URL"
              className="font-mono"
              autoComplete="off" />

            {errors.key &&
            <p className="text-xs text-destructive">{errors.key.message}</p>
            }
            <p className="text-xs text-muted-foreground">
              Uppercase letters, numbers, and underscores only
            </p>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="iconSlug">Icon slug (optional)</Label>
            <Input
              id="iconSlug"
              {...register('iconSlug')}
              placeholder="simple-icons:sqlalchemy"
              className="font-mono"
              autoComplete="off"
            />
            {errors.iconSlug && <p className="text-xs text-destructive">{errors.iconSlug.message}</p>}
            <p className="text-xs text-muted-foreground">Leave blank to auto-detect icon</p>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="value">Value</Label>
            <Controller
              name="value"
              control={control}
              render={({ field }) =>
              <SecretValueEditor
                value={field.value}
                onChange={field.onChange}
                placeholder="Enter secret value..."
                rows={6}
                className="min-h-[160px]"
                autocompleteItems={referenceSuggestions}
              />
              }
            />

            {errors.value &&
            <p className="text-xs text-destructive">{errors.value.message}</p>
            }
            <p className="text-xs text-muted-foreground">
              References: <code className="font-mono">${'{KEY}'}</code>, <code className="font-mono">${'{config.KEY}'}</code>,{' '}
              <code className="font-mono">${'{project.config.KEY}'}</code>
            </p>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}>

              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? 'Saving...' : 'Add Secret'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>);

}
