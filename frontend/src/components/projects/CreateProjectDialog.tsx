import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
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
import { createProject } from '../../lib/api/projects';
import { queryKeys } from '../../lib/api/queryKeys';
const schema = z.object({
  name: z.string().min(1, 'Name is required'),
  slug: z.
  string().
  min(1, 'Slug is required').
  regex(
    /^[a-z0-9-]+$/,
    'Slug must be lowercase letters, numbers, and hyphens only'
  ),
  description: z.string().optional()
});
type FormValues = z.infer<typeof schema>;
interface CreateProjectDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}
export function CreateProjectDialog({
  open,
  onOpenChange
}: CreateProjectDialogProps) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors }
  } = useForm<FormValues>({
    resolver: zodResolver(schema)
  });
  const nameValue = watch('name');
  useEffect(() => {
    if (nameValue) {
      const slug = nameValue.
      toLowerCase().
      replace(/\s+/g, '-').
      replace(/[^a-z0-9-]/g, '');
      setValue('slug', slug);
    }
  }, [nameValue, setValue]);
  const mutation = useMutation({
    mutationFn: createProject,
    onSuccess: (project) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.projects()
      });
      toast.success('Project created');
      reset();
      onOpenChange(false);
      navigate(`/projects/${project.slug}/configs/dev`);
    },
    onError: () => {
      toast.error('Failed to create project');
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
          <DialogTitle>New Project</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 pt-2">
          <div className="space-y-1.5">
            <Label htmlFor="name">Name</Label>
            <Input id="name" {...register('name')} placeholder="My Project" />
            {errors.name &&
            <p className="text-xs text-destructive">{errors.name.message}</p>
            }
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="slug">Slug</Label>
            <Input
              id="slug"
              {...register('slug')}
              placeholder="my-project"
              className="font-mono" />

            {errors.slug &&
            <p className="text-xs text-destructive">{errors.slug.message}</p>
            }
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="description">
              Description{' '}
              <span className="text-muted-foreground">(optional)</span>
            </Label>
            <Textarea
              id="description"
              {...register('description')}
              placeholder="Brief description..."
              rows={2}
              className="resize-none" />

          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}>

              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? 'Creating...' : 'Create Project'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>);

}