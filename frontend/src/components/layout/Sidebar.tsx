import { NavLink, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  LockIcon,
  KeyRoundIcon,
  ScrollTextIcon,
  SettingsIcon,
  LogOutIcon,
  FolderIcon } from
'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { getProjects } from '../../lib/api/projects';
import { queryKeys } from '../../lib/api/queryKeys';
import { useAuth } from '../../lib/auth';
function ProjectNavItem({ slug, name }: {slug: string;name: string;}) {
  const to = `/projects/${slug}/settings`;
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
      `flex items-center gap-2 px-2.5 py-1.5 rounded-md text-sm transition-colors truncate ${isActive ? 'bg-accent text-accent-foreground font-medium' : 'text-muted-foreground hover:bg-accent/50 hover:text-foreground'}`
      }>

      <FolderIcon className="h-3.5 w-3.5 shrink-0" />
      <span className="truncate">{name}</span>
    </NavLink>);

}
export function Sidebar() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const { data: projects = [], isLoading } = useQuery({
    queryKey: queryKeys.projects(),
    queryFn: getProjects
  });
  const handleLogout = () => {
    logout();
    navigate('/login');
  };
  return (
    <aside className="w-60 shrink-0 h-screen flex flex-col border-r border-border bg-muted/30">
      {/* Logo */}
      <div className="flex items-center gap-2 px-4 py-4 border-b border-border">
        <div className="flex items-center justify-center w-7 h-7 rounded-md bg-primary">
          <LockIcon className="h-3.5 w-3.5 text-primary-foreground" />
        </div>
        <span className="font-semibold text-sm tracking-tight">
          Simple Secrets
        </span>
      </div>

      {/* Projects */}
      <div className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
        <div className="px-2 pb-1.5">
          <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Projects
          </span>
        </div>
        {isLoading ?
        Array.from({
          length: 3
        }).map((_, i) =>
        <div key={i} className="px-2.5 py-1.5">
              <Skeleton className="h-4 w-32" />
            </div>
        ) :
        projects.length === 0 ?
        <p className="px-2.5 py-1.5 text-xs text-muted-foreground">
            No projects yet
          </p> :

        projects.map((project) =>
        <ProjectNavItem
          key={project.slug}
          slug={project.slug}
          name={project.name} />

        )
        }
      </div>

      {/* Bottom nav */}
      <div className="border-t border-border py-2 px-2 space-y-0.5">
        <NavLink
          to="/tokens"
          className={({ isActive }) =>
          `flex items-center gap-2 px-2.5 py-1.5 rounded-md text-sm transition-colors ${isActive ? 'bg-accent text-accent-foreground font-medium' : 'text-muted-foreground hover:bg-accent/50 hover:text-foreground'}`
          }>

          <KeyRoundIcon className="h-3.5 w-3.5" />
          Tokens
        </NavLink>
        <NavLink
          to="/audit"
          className={({ isActive }) =>
          `flex items-center gap-2 px-2.5 py-1.5 rounded-md text-sm transition-colors ${isActive ? 'bg-accent text-accent-foreground font-medium' : 'text-muted-foreground hover:bg-accent/50 hover:text-foreground'}`
          }>

          <ScrollTextIcon className="h-3.5 w-3.5" />
          Audit Log
        </NavLink>
        <button
          disabled
          className="flex items-center gap-2 px-2.5 py-1.5 rounded-md text-sm text-muted-foreground/50 w-full cursor-not-allowed">

          <SettingsIcon className="h-3.5 w-3.5" />
          Settings
        </button>
        <div className="pt-1">
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start gap-2 text-muted-foreground hover:text-foreground h-8 px-2.5"
            onClick={handleLogout}>

            <LogOutIcon className="h-3.5 w-3.5" />
            Sign Out
          </Button>
        </div>
      </div>
    </aside>);

}
