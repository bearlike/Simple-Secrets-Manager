import { type LucideIcon, FolderIcon, GroupIcon, KeyRoundIcon, LockIcon, LogOutIcon, ScrollTextIcon, UserIcon, UsersIcon } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';

import {
  Sidebar as SidebarRoot,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSkeleton,
  SidebarRail,
  useSidebar
} from '@/components/ui/sidebar';

import { getProjects } from '../../lib/api/projects';
import { queryKeys } from '../../lib/api/queryKeys';
import { useAuth } from '../../lib/auth';

function isProjectRouteActive(pathname: string, slug: string): boolean {
  return pathname.startsWith(`/projects/${slug}/`);
}

interface NavItemProps {
  icon: LucideIcon;
  isActive: boolean;
  label: string;
  onClick?: () => void;
  to: string;
}

function NavItem({ icon: Icon, isActive, label, onClick, to }: NavItemProps) {
  return (
    <SidebarMenuItem>
      <SidebarMenuButton asChild isActive={isActive} onClick={onClick}>
        <NavLink to={to}>
          <Icon className="h-3.5 w-3.5 shrink-0" />
          <span>{label}</span>
        </NavLink>
      </SidebarMenuButton>
    </SidebarMenuItem>
  );
}

export function Sidebar() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { isMobile, setOpenMobile } = useSidebar();

  const { data: projects = [], isLoading } = useQuery({
    queryKey: queryKeys.projects(),
    queryFn: getProjects
  });

  const closeOnMobile = () => {
    if (isMobile) {
      setOpenMobile(false);
    }
  };

  const handleLogout = () => {
    closeOnMobile();
    logout();
    navigate('/login');
  };

  return (
    <SidebarRoot side="left" variant="sidebar" collapsible="offcanvas">
      <SidebarHeader className="border-b border-sidebar-border px-4 py-4">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-sidebar-primary">
            <LockIcon className="h-3.5 w-3.5 text-sidebar-primary-foreground" />
          </div>
          <span className="text-sm font-semibold tracking-tight">
            Simple Secrets
          </span>
        </div>
      </SidebarHeader>

      <SidebarContent className="gap-0">
        <SidebarGroup className="px-2 py-3">
          <SidebarGroupLabel className="px-2 text-[11px] uppercase tracking-wider">
            Projects
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {isLoading ?
              Array.from({ length: 3 }).map((_, index) =>
                <SidebarMenuItem key={index}>
                  <SidebarMenuSkeleton showIcon />
                </SidebarMenuItem>
              ) :
              projects.length === 0 ?
              <SidebarMenuItem>
                  <SidebarMenuButton disabled>
                    <span>No projects yet</span>
                  </SidebarMenuButton>
                </SidebarMenuItem> :

              projects.map((project) =>
                <SidebarMenuItem key={project.slug}>
                    <SidebarMenuButton
                  asChild
                  isActive={isProjectRouteActive(location.pathname, project.slug)}
                  onClick={closeOnMobile}>

                      <NavLink to={`/projects/${project.slug}/settings`}>
                        <FolderIcon className="h-3.5 w-3.5 shrink-0" />
                        <span className="truncate">{project.name}</span>
                      </NavLink>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
              )
              }
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border p-2">
        <SidebarMenu>
          <NavItem
            to="/account"
            label="Account"
            icon={UserIcon}
            isActive={location.pathname === '/account'}
            onClick={closeOnMobile}
          />
          <NavItem
            to="/team"
            label="Team"
            icon={UsersIcon}
            isActive={location.pathname === '/team'}
            onClick={closeOnMobile}
          />
          <NavItem
            to="/groups"
            label="Groups"
            icon={GroupIcon}
            isActive={location.pathname === '/groups'}
            onClick={closeOnMobile}
          />
          <NavItem
            to="/tokens"
            label="Tokens"
            icon={KeyRoundIcon}
            isActive={location.pathname === '/tokens'}
            onClick={closeOnMobile}
          />
          <NavItem
            to="/audit"
            label="Audit Log"
            icon={ScrollTextIcon}
            isActive={location.pathname === '/audit'}
            onClick={closeOnMobile}
          />
          <SidebarMenuItem>
            <SidebarMenuButton onClick={handleLogout}>
              <LogOutIcon className="h-3.5 w-3.5 shrink-0" />
              <span>Sign Out</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </SidebarRoot>
  );
}
