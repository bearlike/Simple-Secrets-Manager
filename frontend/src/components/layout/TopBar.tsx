import { useParams, useNavigate, useLocation, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ChevronRightIcon,
  DownloadIcon,
  GithubIcon,
  LogOutIcon,
  MoonIcon,
  SettingsIcon,
  SunIcon,
  UserCircle2Icon,
  UsersIcon,
  GroupIcon
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select';
import { getProjects } from '../../lib/api/projects';
import { getConfigs } from '../../lib/api/configs';
import { bulkExport } from '../../lib/api/secrets';
import { getAppVersion } from '../../lib/api/version';
import { getMe } from '../../lib/api/me';
import { queryKeys } from '../../lib/api/queryKeys';
import { useTheme } from '../../lib/theme';
import { useAuth } from '../../lib/auth';
import { notifyApiError } from '../../lib/api/errorToast';

const REPOSITORY_URL = 'https://github.com/bearlike/Simple-Secrets-Manager';

function downloadFile(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function TopBar() {
  const { projectSlug, configSlug } = useParams<{
    projectSlug?: string;
    configSlug?: string;
  }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();
  const { logout } = useAuth();
  const isCompareBySecretPage = Boolean(projectSlug) && location.pathname.endsWith('/compare/secret');

  const { data: projects = [] } = useQuery({
    queryKey: queryKeys.projects(),
    queryFn: getProjects,
    enabled: !!projectSlug
  });

  const { data: configs = [] } = useQuery({
    queryKey: queryKeys.configs(projectSlug ?? ''),
    queryFn: () => getConfigs(projectSlug ?? ''),
    enabled: !!projectSlug
  });
  const { data: appVersion = 'unknown' } = useQuery({
    queryKey: queryKeys.appVersion(),
    queryFn: getAppVersion,
    staleTime: 5 * 60 * 1000
  });
  const { data: me } = useQuery({
    queryKey: queryKeys.me(),
    queryFn: getMe
  });

  const currentProject = projects.find((project) => project.slug === projectSlug);

  const handleConfigChange = (newConfigSlug: string) => {
    if (projectSlug) {
      navigate(`/projects/${projectSlug}/configs/${newConfigSlug}`);
    }
  };

  const handleExport = async (format: 'json' | 'env', raw = false) => {
    if (!projectSlug || !configSlug) return;

    try {
      const result = await bulkExport(projectSlug, configSlug, format, {
        resolveReferences: !raw,
        raw
      });
      if (result.format === 'json') {
        downloadFile(
          JSON.stringify(result.data, null, 2),
          `${projectSlug}-${configSlug}.json`,
          'application/json'
        );
      } else {
        downloadFile(result.data, `${projectSlug}-${configSlug}.env`, 'text/plain');
      }
      toast.success(`Exported as ${format.toUpperCase()}${raw ? ' (raw)' : ''}`);
    } catch (error) {
      notifyApiError(error, 'Export failed');
    }
  };

  return (
    <header className="h-12 border-b border-border bg-background flex items-center px-4 gap-3 shrink-0">
      <nav className="flex items-center gap-1.5 text-sm flex-1 min-w-0">
        <Link
          to="/projects"
          className="text-muted-foreground hover:text-foreground transition-colors shrink-0"
        >
          Projects
        </Link>

        {projectSlug && (
          <>
            <ChevronRightIcon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            <Link
              to={`/projects/${projectSlug}/settings`}
              className="text-muted-foreground hover:text-foreground transition-colors truncate max-w-[120px]"
            >
              {currentProject?.name ?? projectSlug}
            </Link>
          </>
        )}

        {configSlug && (
          <>
            <ChevronRightIcon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            <span className="font-medium text-foreground font-mono text-xs">{configSlug}</span>
          </>
        )}

        {isCompareBySecretPage && (
          <>
            <ChevronRightIcon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            <span className="text-muted-foreground">Compare</span>
            <ChevronRightIcon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            <span className="font-medium text-foreground text-xs">By Secret</span>
          </>
        )}
      </nav>

      {projectSlug && configs.length > 0 && (
        <Select value={configSlug} onValueChange={handleConfigChange}>
          <SelectTrigger className="h-7 w-32 text-xs font-mono">
            <SelectValue placeholder="Select config" />
          </SelectTrigger>
          <SelectContent>
            {configs.map((config) => (
              <SelectItem key={config.slug} value={config.slug} className="text-xs font-mono">
                {config.slug}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}

      <Button variant="outline" size="sm" className="h-7 gap-1.5 text-xs" asChild>
        <a
          href={REPOSITORY_URL}
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Open repository on GitHub"
        >
          <GithubIcon className="h-3.5 w-3.5" />
          {`GitHub v${appVersion}`}
        </a>
      </Button>

      <Button
        variant="ghost"
        size="sm"
        className="h-7 w-7 p-0 text-muted-foreground"
        onClick={toggleTheme}
        aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      >
        {theme === 'dark' ? <SunIcon className="h-3.5 w-3.5" /> : <MoonIcon className="h-3.5 w-3.5" />}
      </Button>

      {projectSlug && (
        <Button
          variant="ghost"
          size="sm"
          className="h-7 w-7 p-0 text-muted-foreground"
          onClick={() => navigate(`/projects/${projectSlug}/settings`)}
          aria-label="Project settings"
        >
          <SettingsIcon className="h-3.5 w-3.5" />
        </Button>
      )}

      {projectSlug && configSlug && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" className="h-7 gap-1.5 text-xs">
              <DownloadIcon className="h-3.5 w-3.5" />
              Export
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => handleExport('json')}>Export as JSON (resolved)</DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleExport('env')}>Export as .env (resolved)</DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleExport('json', true)}>Export as JSON (raw)</DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleExport('env', true)}>Export as .env (raw)</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      )}

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm" className="h-7 gap-1.5 px-2 text-xs">
            <UserCircle2Icon className="h-4 w-4" />
            <span className="max-w-28 truncate">{me?.username ?? 'Account'}</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={() => navigate('/account')}>
            <UserCircle2Icon className="h-3.5 w-3.5 mr-2" />
            Account
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => navigate('/team')}>
            <UsersIcon className="h-3.5 w-3.5 mr-2" />
            Team
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => navigate('/groups')}>
            <GroupIcon className="h-3.5 w-3.5 mr-2" />
            Groups
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={() => {
              logout();
              navigate('/login');
            }}
          >
            <LogOutIcon className="h-3.5 w-3.5 mr-2" />
            Sign Out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}
