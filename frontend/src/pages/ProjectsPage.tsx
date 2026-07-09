import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  PlusIcon,
  FolderIcon,
  MoreVerticalIcon,
  PencilIcon,
  Trash2Icon,
  ArchiveIcon,
  ArchiveRestoreIcon } from
'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue } from
'@/components/ui/select';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle } from
'@/components/ui/card';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger } from
'@/components/ui/dropdown-menu';
import { Skeleton } from '@/components/ui/skeleton';
import { getProjects, getArchivedProjects, deleteProject, updateProject } from '../lib/api/projects';
import { getConfigs } from '../lib/api/configs';
import { queryKeys } from '../lib/api/queryKeys';
import { CreateProjectDialog } from '../components/projects/CreateProjectDialog';
import { EditProjectDialog } from '../components/projects/EditProjectDialog';
import { ConfirmDialog } from '../components/common/ConfirmDialog';
import { EmptyState } from '../components/common/EmptyState';
import { notifyApiError } from '../lib/api/errorToast';
import type { Project } from '../lib/api/types';
function ProjectCard({
  project,
  onEdit,
  onDelete
}: {project: Project;onEdit: (project: Project) => void;onDelete: (project: Project) => void;}) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: configs = [] } = useQuery({
    queryKey: queryKeys.configs(project.slug),
    queryFn: () => getConfigs(project.slug)
  });
  const archiveMutation = useMutation({
    mutationFn: () => updateProject(project.slug, { archived: !project.archived }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects() });
      toast.success(project.archived ? 'Project unarchived' : 'Project archived');
    },
    onError: (error) => {
      notifyApiError(
        error,
        project.archived ? 'Failed to unarchive project' : 'Failed to archive project'
      );
    }
  });
  const handleClick = () => {
    navigate(`/projects/${project.slug}/settings`);
  };
  return (
    <Card
      className="cursor-pointer hover:shadow-sm transition-shadow border-border"
      onClick={handleClick}>

      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <FolderIcon className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-sm font-semibold">
              {project.name}
            </CardTitle>
            {project.archived &&
            <Badge variant="secondary" className="text-[10px] font-normal">
                Archived
              </Badge>
            }
          </div>
          <div className="flex items-center gap-1">
            <span className="text-xs text-muted-foreground">
              {configs.length} config{configs.length !== 1 ? 's' : ''}
            </span>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6 text-muted-foreground"
                  onClick={(event) => event.stopPropagation()}
                  aria-label={`Actions for ${project.slug}`}>

                  <MoreVerticalIcon className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="end"
                onClick={(event) => event.stopPropagation()}>

                <DropdownMenuItem onSelect={() => onEdit(project)}>
                  <PencilIcon className="h-3.5 w-3.5 mr-2" />
                  Edit
                </DropdownMenuItem>
                <DropdownMenuItem
                  disabled={archiveMutation.isPending}
                  onSelect={() => archiveMutation.mutate()}>

                  {project.archived ?
                  <>
                      <ArchiveRestoreIcon className="h-3.5 w-3.5 mr-2" />
                      Unarchive
                    </> :

                  <>
                      <ArchiveIcon className="h-3.5 w-3.5 mr-2" />
                      Archive
                    </>
                  }
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  className="text-destructive focus:text-destructive"
                  onSelect={() => onDelete(project)}>

                  <Trash2Icon className="h-3.5 w-3.5 mr-2" />
                  Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
        <code className="text-xs text-muted-foreground font-mono">
          {project.slug}
        </code>
      </CardHeader>
      <CardContent className="pt-0">
        {project.description &&
        <CardDescription className="text-xs line-clamp-2">
            {project.description}
          </CardDescription>
        }
        <p className="text-xs text-muted-foreground mt-2">
          Created {project.createdAt ? new Date(project.createdAt).toLocaleDateString() : '-'}
        </p>
      </CardContent>
    </Card>);

}
export function ProjectsPage() {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Project | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Project | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const { data: projects = [], isLoading } = useQuery({
    queryKey: queryKeys.projects(showArchived),
    queryFn: showArchived ? getArchivedProjects : getProjects
  });
  const deleteMutation = useMutation({
    mutationFn: (slug: string) => deleteProject(slug),
    onSuccess: (_data, slug) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects() });
      queryClient.removeQueries({ queryKey: queryKeys.configs(slug) });
      toast.success('Project deleted');
      setDeleteTarget(null);
    },
    onError: (error) => {
      notifyApiError(error, 'Failed to delete project');
    }
  });
  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-lg font-semibold">Projects</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Manage your secret namespaces
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select
            value={showArchived ? 'archived' : 'active'}
            onValueChange={(value) => setShowArchived(value === 'archived')}>

            <SelectTrigger className="h-8 w-28 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="archived">Archived</SelectItem>
            </SelectContent>
          </Select>
          <Button
            size="sm"
            className="gap-1.5"
            onClick={() => setCreateOpen(true)}>

            <PlusIcon className="h-3.5 w-3.5" />
            New Project
          </Button>
        </div>
      </div>

      {isLoading ?
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({
          length: 3
        }).map((_, i) =>
        <Card key={i}>
              <CardHeader className="pb-2">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-3 w-20 mt-1" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-24 mt-2" />
              </CardContent>
            </Card>
        )}
        </div> :
      projects.length === 0 ?
      <EmptyState
        icon={FolderIcon}
        title={showArchived ? 'No archived projects' : 'No projects yet'}
        description={
        showArchived ?
        'Projects you archive will appear here' :
        'Create your first project to start managing secrets'
        }
        action={
        showArchived ?
        undefined :
        <Button size="sm" onClick={() => setCreateOpen(true)}>
              <PlusIcon className="h-3.5 w-3.5 mr-1.5" />
              New Project
            </Button>
        } /> :


      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((project) =>
        <ProjectCard
          key={project.slug}
          project={project}
          onEdit={setEditTarget}
          onDelete={setDeleteTarget} />

        )}
        </div>
      }

      <CreateProjectDialog open={createOpen} onOpenChange={setCreateOpen} />
      <EditProjectDialog
        project={editTarget}
        open={editTarget !== null}
        onOpenChange={(open) => {
          if (!open) setEditTarget(null);
        }} />

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        title="Delete project"
        description={
        deleteTarget ?
        `Delete "${deleteTarget.name}" and all of its configs and secrets? This can't be undone.` :
        ''
        }
        destructive
        loading={deleteMutation.isPending}
        onConfirm={() => {
          if (deleteTarget) deleteMutation.mutate(deleteTarget.slug);
        }} />

    </div>);

}
