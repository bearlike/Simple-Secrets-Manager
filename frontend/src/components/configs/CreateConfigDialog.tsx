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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue } from
'@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { createConfig } from '../../lib/api/configs';
import { queryKeys } from '../../lib/api/queryKeys';
import type { Config } from '../../lib/api/types';
import { notifyApiError } from '../../lib/api/errorToast';
const schema = z.object({
  name: z.string().min(1, 'Name is required'),
  slug: z.
  string().
  min(1, 'Slug is required').
  regex(
    /^[a-z0-9-]+$/,
    'Slug must be lowercase letters, numbers, and hyphens only'
  ),
  parentSlug: z.string().optional()
});
type FormValues = z.infer<typeof schema>;
interface CreateConfigDialogProps {
  projectSlug: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  existingConfigs: Config[];
}
export function CreateConfigDialog({
  projectSlug,
  open,
  onOpenChange,
  existingConfigs
}: CreateConfigDialogProps) {
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
  const parentSlug = watch('parentSlug');
  const mutation = useMutation({
    mutationFn: (data: FormValues) =>
    createConfig(projectSlug, {
      name: data.name,
      slug: data.slug,
      parentSlug: data.parentSlug || undefined
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.configs(projectSlug)
      });
      toast.success('Config created');
      reset();
      onOpenChange(false);
    },
    onError: (error) => {
      notifyApiError(error, 'Failed to create config');
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
          <DialogTitle>New Config</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 pt-2">
          <div className="space-y-1.5">
            <Label htmlFor="cfg-name">Name</Label>
            <Input
              id="cfg-name"
              {...register('name')}
              placeholder="Production" />

            {errors.name &&
            <p className="text-xs text-destructive">{errors.name.message}</p>
            }
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cfg-slug">Slug</Label>
            <Input
              id="cfg-slug"
              {...register('slug')}
              placeholder="prod"
              className="font-mono" />

            {errors.slug &&
            <p className="text-xs text-destructive">{errors.slug.message}</p>
            }
          </div>
          {existingConfigs.length > 0 &&
          <div className="space-y-1.5">
              <Label>
                Parent Config{' '}
                <span className="text-muted-foreground">(optional)</span>
              </Label>
              <Select
              onValueChange={(val) =>
              setValue('parentSlug', val === 'none' ? undefined : val)
              }>

                <SelectTrigger>
                  <SelectValue placeholder="No parent (root config)" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">No parent</SelectItem>
                  {existingConfigs.map((c) =>
                <SelectItem key={c.slug} value={c.slug}>
                      {c.name}
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
              {mutation.isPending ? 'Creating...' : 'Create Config'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>);

}
