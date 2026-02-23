import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { CheckIcon, ClipboardIcon, AlertTriangleIcon } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select';
import { createToken } from '../../lib/api/tokens';
import { getConfigs } from '../../lib/api/configs';
import { queryKeys } from '../../lib/api/queryKeys';
import type { Project } from '../../lib/api/types';

const schema = z
  .object({
    type: z.enum(['service', 'personal']),
    serviceName: z.string().optional(),
    projectSlug: z.string().optional(),
    configSlug: z.string().optional(),
    access: z.enum(['read', 'read_write']),
    ttlHours: z.preprocess(
      (value) => {
        if (value === '' || value === undefined || value === null) return undefined;
        return Number(value);
      },
      z.number().int().positive('TTL must be greater than 0').max(24 * 365).optional()
    )
  })
  .superRefine((value, ctx) => {
    if (value.type === 'service' && !value.serviceName?.trim()) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['serviceName'],
        message: 'Service name is required for service tokens'
      });
    }
  });

type FormValues = z.infer<typeof schema>;

interface CreateTokenDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projects: Project[];
}

export function CreateTokenDialog({ open, onOpenChange, projects }: CreateTokenDialogProps) {
  const queryClient = useQueryClient();
  const [plaintext, setPlaintext] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const {
    handleSubmit,
    watch,
    setValue,
    reset,
    register,
    formState: { errors }
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      type: 'service',
      access: 'read'
    }
  });

  const selectedType = watch('type');
  const selectedProject = watch('projectSlug');

  const { data: configs = [] } = useQuery({
    queryKey: queryKeys.configs(selectedProject ?? ''),
    queryFn: () => getConfigs(selectedProject ?? ''),
    enabled: !!selectedProject
  });

  const mutation = useMutation({
    mutationFn: createToken,
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tokens() });
      if (response.plaintext) {
        setPlaintext(response.plaintext);
      } else {
        toast.success('Token created');
        handleClose();
      }
    },
    onError: () => {
      toast.error('Failed to create token');
    }
  });

  const onSubmit = (data: FormValues) => {
    mutation.mutate({
      type: data.type,
      serviceName: data.type === 'service' ? data.serviceName : undefined,
      projectSlug: data.projectSlug || undefined,
      configSlug: data.configSlug || undefined,
      access: data.access,
      ttlSeconds: data.ttlHours ? data.ttlHours * 3600 : undefined
    });
  };

  const handleCopy = () => {
    if (!plaintext) return;

    navigator.clipboard.writeText(plaintext).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const handleClose = () => {
    onOpenChange(false);
    setTimeout(() => {
      reset();
      setPlaintext(null);
      setCopied(false);
    }, 200);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>{plaintext ? 'Token Created' : 'New Access Token'}</DialogTitle>
        </DialogHeader>

        {plaintext ? (
          <div className="space-y-4 pt-2">
            <Alert className="border-yellow-200 bg-yellow-50">
              <AlertTriangleIcon className="h-4 w-4 text-yellow-600" />
              <AlertDescription className="text-yellow-800 text-sm">
                This token will only be shown once. Copy it now.
              </AlertDescription>
            </Alert>

            <div className="space-y-2">
              <Label className="text-xs text-muted-foreground">Your Token</Label>
              <div className="flex items-center gap-2 p-3 rounded-md bg-muted border border-border">
                <code className="flex-1 font-mono text-xs break-all text-foreground">{plaintext}</code>
                <Button variant="outline" size="sm" className="shrink-0 h-7 gap-1.5" onClick={handleCopy}>
                  {copied ? (
                    <CheckIcon className="h-3.5 w-3.5 text-green-600" />
                  ) : (
                    <ClipboardIcon className="h-3.5 w-3.5" />
                  )}
                  {copied ? 'Copied' : 'Copy'}
                </Button>
              </div>
            </div>

            <DialogFooter>
              <Button onClick={handleClose}>Done</Button>
            </DialogFooter>
          </div>
        ) : (
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 pt-2">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Type</Label>
                <Select
                  defaultValue="service"
                  onValueChange={(value) => {
                    setValue('type', value as 'service' | 'personal');
                    if (value === 'personal') {
                      setValue('serviceName', undefined);
                    }
                  }}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="service">Service</SelectItem>
                    <SelectItem value="personal">Personal</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label>Access</Label>
                <Select
                  defaultValue="read"
                  onValueChange={(value) => setValue('access', value as 'read' | 'read_write')}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="read">Read Only</SelectItem>
                    <SelectItem value="read_write">Read &amp; Write</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {selectedType === 'service' && (
              <div className="space-y-1.5">
                <Label htmlFor="service-name">Service Name</Label>
                <Input id="service-name" {...register('serviceName')} placeholder="ci-runner" />
                {errors.serviceName && (
                  <p className="text-xs text-destructive">{errors.serviceName.message}</p>
                )}
              </div>
            )}

            <div className="space-y-1.5">
              <Label>
                Project <span className="text-muted-foreground">(optional)</span>
              </Label>
              <Select
                onValueChange={(value) => {
                  setValue('projectSlug', value === 'none' ? undefined : value);
                  setValue('configSlug', undefined);
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="All projects" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">All projects</SelectItem>
                  {projects.map((project) => (
                    <SelectItem key={project.slug} value={project.slug}>
                      {project.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {selectedProject && configs.length > 0 && (
              <div className="space-y-1.5">
                <Label>
                  Config <span className="text-muted-foreground">(optional)</span>
                </Label>
                <Select
                  onValueChange={(value) => setValue('configSlug', value === 'none' ? undefined : value)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="All configs" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">All configs</SelectItem>
                    {configs.map((config) => (
                      <SelectItem key={config.slug} value={config.slug}>
                        {config.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            <div className="space-y-1.5">
              <Label htmlFor="ttl-hours">
                TTL Hours <span className="text-muted-foreground">(optional)</span>
              </Label>
              <Input
                id="ttl-hours"
                type="number"
                min={1}
                step={1}
                placeholder="24"
                {...register('ttlHours')}
              />
              {errors.ttlHours && <p className="text-xs text-destructive">{errors.ttlHours.message}</p>}
            </div>

            <DialogFooter>
              <Button type="button" variant="outline" onClick={handleClose}>
                Cancel
              </Button>
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending ? 'Creating...' : 'Create Token'}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
