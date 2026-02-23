import { useForm } from 'react-hook-form';
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
import { Textarea } from '@/components/ui/textarea';
import { createSecret } from '../../lib/api/secrets';
import { queryKeys } from '../../lib/api/queryKeys';
const schema = z.object({
  key: z.
  string().
  min(1, 'Key is required').
  regex(
    /^[A-Z0-9_]+$/,
    'Key must be uppercase letters, numbers, and underscores only'
  ),
  value: z.string().min(1, 'Value is required')
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
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors }
  } = useForm<FormValues>({
    resolver: zodResolver(schema)
  });
  const mutation = useMutation({
    mutationFn: (data: FormValues) =>
    createSecret(projectSlug, configSlug, data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.secrets(projectSlug, configSlug)
      });
      toast.success('Secret created');
      reset();
      onOpenChange(false);
    },
    onError: () => {
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

      <DialogContent className="sm:max-w-[480px]">
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
            <Label htmlFor="value">Value</Label>
            <Textarea
              id="value"
              {...register('value')}
              placeholder="Enter secret value..."
              className="font-mono text-sm resize-none"
              rows={3} />

            {errors.value &&
            <p className="text-xs text-destructive">{errors.value.message}</p>
            }
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