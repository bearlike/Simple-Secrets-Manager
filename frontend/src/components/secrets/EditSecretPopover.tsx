import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { updateSecret } from '../../lib/api/secrets';
import { queryKeys } from '../../lib/api/queryKeys';
import type { Secret } from '../../lib/api/types';
const schema = z.object({
  value: z.string().min(1, 'Value is required')
});
type FormValues = z.infer<typeof schema>;
interface EditSecretPopoverProps {
  secret: Secret;
  projectSlug: string;
  configSlug: string;
  onClose: () => void;
}
export function EditSecretPopover({
  secret,
  projectSlug,
  configSlug,
  onClose
}: EditSecretPopoverProps) {
  const queryClient = useQueryClient();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors }
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      value: secret.value
    }
  });
  useEffect(() => {
    reset({
      value: secret.value
    });
  }, [secret.key, reset, secret.value]);
  const mutation = useMutation({
    mutationFn: (data: FormValues) =>
    updateSecret(projectSlug, configSlug, secret.key, data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.secrets(projectSlug, configSlug)
      });
      toast.success('Secret updated');
      onClose();
    },
    onError: () => {
      toast.error('Failed to update secret');
    }
  });
  const onSubmit = (data: FormValues) => mutation.mutate(data);
  return (
    <div className="p-3 space-y-3 w-72">
      <div className="space-y-1">
        <Label className="text-xs text-muted-foreground">Editing</Label>
        <p className="font-mono text-sm font-medium">{secret.key}</p>
      </div>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-2">
        <div className="space-y-1">
          <Textarea
            {...register('value')}
            className="font-mono text-sm resize-none"
            rows={3}
            autoFocus
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                handleSubmit(onSubmit)();
              }
              if (e.key === 'Escape') onClose();
            }} />

          {errors.value &&
          <p className="text-xs text-destructive">{errors.value.message}</p>
          }
          <p className="text-xs text-muted-foreground">
            References: <code className="font-mono">${'{KEY}'}</code>, <code className="font-mono">${'{config.KEY}'}</code>,{' '}
            <code className="font-mono">${'{project.config.KEY}'}</code>
          </p>
          <p className="text-xs text-muted-foreground">
            ⌘+Enter to save, Esc to cancel
          </p>
        </div>
        <div className="flex gap-2 justify-end">
          <Button type="button" variant="outline" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" size="sm" disabled={mutation.isPending}>
            {mutation.isPending ? 'Saving...' : 'Save'}
          </Button>
        </div>
      </form>
    </div>);

}
