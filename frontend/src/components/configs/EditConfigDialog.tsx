import { useEffect } from 'react';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue } from
'@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { updateConfig } from '../../lib/api/configs';
import { queryKeys } from '../../lib/api/queryKeys';
import type { Config } from '../../lib/api/types';
import { notifyApiError } from '../../lib/api/errorToast';

const NO_PARENT = 'none';

const schema = z.object({
  name: z.string().min(1, 'Name is required'),
  parentSlug: z.string().optional(),
  description: z.string().optional()
});
type FormValues = z.infer<typeof schema>;

interface EditConfigDialogProps {
  projectSlug: string;
  config: Config | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  existingConfigs: Config[];
}

export function EditConfigDialog({
  projectSlug,
  config,
  open,
  onOpenChange,
  existingConfigs
}: EditConfigDialogProps) {
  const queryClient = useQueryClient();
  const {
    register,
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors }
  } = useForm<FormValues>({
    resolver: zodResolver(schema)
  });

  useEffect(() => {
    if (open && config) {
      reset({
        name: config.name,
        parentSlug: config.parentSlug ?? undefined,
        description: config.description ?? ''
      });
    }
  }, [open, config, reset]);

  const parentSlug = watch('parentSlug');
  // A config cannot inherit from itself.
  const parentOptions = existingConfigs.filter(
    (candidate) => candidate.slug !== config?.slug
  );

  const mutation = useMutation({
    mutationFn: (data: FormValues) => {
      if (!config) {
        return Promise.reject(new Error('No config selected'));
      }
      return updateConfig(projectSlug, config.slug, {
        name: data.name,
        parentSlug: data.parentSlug ?? null,
        description: data.description ?? ''
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.configs(projectSlug)
      });
      toast.success('Config updated');
      onOpenChange(false);
    },
    onError: (error) => {
      notifyApiError(error, 'Failed to update config');
    }
  });

  const onSubmit = (data: FormValues) => mutation.mutate(data);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>Edit Config</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 pt-2">
          <div className="space-y-1.5">
            <Label htmlFor="edit-cfg-name">Name</Label>
            <Input
              id="edit-cfg-name"
              {...register('name')}
              placeholder="Production" />

            {errors.name &&
            <p className="text-xs text-destructive">{errors.name.message}</p>
            }
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="edit-cfg-slug">Slug</Label>
            <Input
              id="edit-cfg-slug"
              value={config?.slug ?? ''}
              readOnly
              disabled
              className="font-mono" />

            <p className="text-xs text-muted-foreground">
              The slug is the config's identifier and can't be changed.
            </p>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="edit-cfg-description">
              Description{' '}
              <span className="text-muted-foreground">(optional)</span>
            </Label>
            <Textarea
              id="edit-cfg-description"
              {...register('description')}
              placeholder="What this config is for..."
              rows={2}
              className="resize-none" />

          </div>
          {parentOptions.length > 0 &&
          <div className="space-y-1.5">
              <Label>
                Parent Config{' '}
                <span className="text-muted-foreground">(optional)</span>
              </Label>
              <Select
              value={parentSlug ?? NO_PARENT}
              onValueChange={(val) =>
              setValue('parentSlug', val === NO_PARENT ? undefined : val)
              }>

                <SelectTrigger>
                  <SelectValue placeholder="No parent (root config)" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NO_PARENT}>No parent</SelectItem>
                  {parentOptions.map((candidate) =>
                <SelectItem key={candidate.slug} value={candidate.slug}>
                      {candidate.name}
                    </SelectItem>
                )}
                </SelectContent>
              </Select>
              {parentSlug &&
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <span>Inherits from</span>
                  <Badge variant="outline" className="text-xs font-mono">
                    {parentSlug}
                  </Badge>
                </div>
            }
            </div>
          }
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}>

              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? 'Saving...' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>);

}
