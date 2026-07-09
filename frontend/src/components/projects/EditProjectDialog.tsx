import { useEffect } from 'react';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue } from
'@/components/ui/select';
import { updateProject } from '../../lib/api/projects';
import { queryKeys } from '../../lib/api/queryKeys';
import { notifyApiError } from '../../lib/api/errorToast';
import type { Project } from '../../lib/api/types';

const schema = z.object({
  name: z.string().min(1, 'Name is required'),
  archived: z.boolean()
});
type FormValues = z.infer<typeof schema>;

interface EditProjectDialogProps {
  project: Project | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function EditProjectDialog({
  project,
  open,
  onOpenChange
}: EditProjectDialogProps) {
  const queryClient = useQueryClient();
  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors }
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: '', archived: false }
  });

  useEffect(() => {
    if (open && project) {
      reset({ name: project.name, archived: Boolean(project.archived) });
    }
  }, [open, project, reset]);

  const mutation = useMutation({
    mutationFn: (data: FormValues) => {
      if (!project) {
        return Promise.reject(new Error('No project selected'));
      }
      return updateProject(project.slug, {
        name: data.name,
        archived: data.archived
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects() });
      toast.success('Project updated');
      onOpenChange(false);
    },
    onError: (error) => {
      notifyApiError(error, 'Failed to update project');
    }
  });

  const onSubmit = (data: FormValues) => mutation.mutate(data);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>Edit Project</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 pt-2">
          <div className="space-y-1.5">
            <Label htmlFor="edit-project-name">Name</Label>
            <Input
              id="edit-project-name"
              {...register('name')}
              placeholder="My Project" />

            {errors.name &&
            <p className="text-xs text-destructive">{errors.name.message}</p>
            }
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="edit-project-status">Status</Label>
            <Controller
              control={control}
              name="archived"
              render={({ field }) =>
              <Select
                value={field.value ? 'archived' : 'active'}
                onValueChange={(value) => field.onChange(value === 'archived')}>

                  <SelectTrigger id="edit-project-status">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="archived">Archived</SelectItem>
                  </SelectContent>
                </Select>
              } />

          </div>
          <div className="space-y-1.5">
            <Label htmlFor="edit-project-slug">Slug</Label>
            <Input
              id="edit-project-slug"
              value={project?.slug ?? ''}
              readOnly
              disabled
              className="font-mono" />

            <p className="text-xs text-muted-foreground">
              The slug is the project's identifier and can't be changed.
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
              {mutation.isPending ? 'Saving...' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>);

}
