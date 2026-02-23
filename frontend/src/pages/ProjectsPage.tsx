import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { PlusIcon, FolderIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle } from
'@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { getProjects } from '../lib/api/projects';
import { getConfigs } from '../lib/api/configs';
import { queryKeys } from '../lib/api/queryKeys';
import { CreateProjectDialog } from '../components/projects/CreateProjectDialog';
import { EmptyState } from '../components/common/EmptyState';
import type { Project } from '../lib/api/types';
function ProjectCard({ project }: {project: Project;}) {
  const navigate = useNavigate();
  const { data: configs = [] } = useQuery({
    queryKey: queryKeys.configs(project.slug),
    queryFn: () => getConfigs(project.slug)
  });
  const defaultConfig = configs.find((c) => c.slug === 'dev') ?? configs[0];
  const handleClick = () => {
    const configSlug = defaultConfig?.slug ?? 'dev';
    navigate(`/projects/${project.slug}/configs/${configSlug}`);
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
          </div>
          <span className="text-xs text-muted-foreground">
            {configs.length} config{configs.length !== 1 ? 's' : ''}
          </span>
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
  const [createOpen, setCreateOpen] = useState(false);
  const { data: projects = [], isLoading } = useQuery({
    queryKey: queryKeys.projects(),
    queryFn: getProjects
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
        <Button
          size="sm"
          className="gap-1.5"
          onClick={() => setCreateOpen(true)}>

          <PlusIcon className="h-3.5 w-3.5" />
          New Project
        </Button>
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
        title="No projects yet"
        description="Create your first project to start managing secrets"
        action={
        <Button size="sm" onClick={() => setCreateOpen(true)}>
              <PlusIcon className="h-3.5 w-3.5 mr-1.5" />
              New Project
            </Button>
        } /> :


      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((project) =>
        <ProjectCard key={project.slug} project={project} />
        )}
        </div>
      }

      <CreateProjectDialog open={createOpen} onOpenChange={setCreateOpen} />
    </div>);

}
