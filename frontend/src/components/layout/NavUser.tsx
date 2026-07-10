import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  ChevronsUpDownIcon,
  ExternalLinkIcon,
  GroupIcon,
  LogOutIcon,
  UserIcon,
  UsersIcon
} from 'lucide-react';

import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu';
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar
} from '@/components/ui/sidebar';

import { getMe } from '../../lib/api/me';
import { getAppVersion } from '../../lib/api/version';
import { queryKeys } from '../../lib/api/queryKeys';
import { useAuth } from '../../lib/auth';
import { useTheme } from '../../lib/theme';

const REPOSITORY_URL = 'https://github.com/bearlike/Simple-Secrets-Manager';

function getInitials(username: string): string {
  const parts = username.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function UserAvatar({ username }: { username?: string | null }) {
  const initials = username ? getInitials(username) : '';
  return (
    <div
      aria-hidden
      className="flex aspect-square size-8 shrink-0 items-center justify-center rounded-lg bg-sidebar-primary text-xs font-semibold text-sidebar-primary-foreground"
    >
      {initials || <UserIcon className="size-4" />}
    </div>
  );
}

export function NavUser() {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const { theme, setTheme } = useTheme();
  const { isMobile, setOpenMobile } = useSidebar();

  const { data: me } = useQuery({
    queryKey: queryKeys.me(),
    queryFn: getMe
  });

  const { data: appVersion } = useQuery({
    queryKey: queryKeys.appVersion(),
    queryFn: getAppVersion,
    staleTime: 5 * 60 * 1000
  });

  const displayName = me?.username ?? 'Account';

  const closeOnMobile = () => {
    if (isMobile) {
      setOpenMobile(false);
    }
  };

  const goTo = (path: string) => {
    closeOnMobile();
    navigate(path);
  };

  const handleLogout = () => {
    closeOnMobile();
    logout();
    navigate('/login');
  };

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              size="lg"
              aria-label={`${displayName} account menu`}
              className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
            >
              <UserAvatar username={me?.username} />
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-semibold">{displayName}</span>
                {me?.workspaceRole && (
                  <span className="truncate text-xs capitalize text-sidebar-foreground/70">
                    {me.workspaceRole}
                  </span>
                )}
              </div>
              <ChevronsUpDownIcon className="ml-auto size-4" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-[--radix-dropdown-menu-trigger-width] min-w-56 rounded-lg"
            side={isMobile ? 'bottom' : 'right'}
            align="end"
            sideOffset={4}
          >
            <DropdownMenuLabel className="p-0 font-normal">
              <div className="flex items-center gap-2 px-1 py-1.5 text-left text-sm">
                <UserAvatar username={me?.username} />
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-semibold">{displayName}</span>
                  {me?.email && (
                    <span className="truncate text-xs text-muted-foreground">
                      {me.email}
                    </span>
                  )}
                </div>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuItem onClick={() => goTo('/account')}>
                <UserIcon />
                Account
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => goTo('/team')}>
                <UsersIcon />
                Team
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => goTo('/groups')}>
                <GroupIcon />
                Groups
              </DropdownMenuItem>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuCheckboxItem
                checked={theme === 'dark'}
                onCheckedChange={(checked) => setTheme(checked ? 'dark' : 'light')}
                onSelect={(event) => event.preventDefault()}
              >
                Dark mode
              </DropdownMenuCheckboxItem>
              <DropdownMenuItem asChild>
                <a
                  href={REPOSITORY_URL}
                  target="_blank"
                  rel="noreferrer"
                  aria-label={
                    appVersion
                      ? `Open GitHub repository (v${appVersion}) in a new tab`
                      : 'Open GitHub repository in a new tab'
                  }
                >
                  <ExternalLinkIcon />
                  {appVersion ? `GitHub v${appVersion}` : 'GitHub'}
                </a>
              </DropdownMenuItem>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleLogout}>
              <LogOutIcon />
              Sign Out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
