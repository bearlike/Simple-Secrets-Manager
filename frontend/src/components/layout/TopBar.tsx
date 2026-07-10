import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { DownloadIcon, EllipsisIcon, SettingsIcon } from 'lucide-react';
import { toast } from 'sonner';
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator
} from '@/components/ui/breadcrumb';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu';
import { SidebarTrigger } from '@/components/ui/sidebar';
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
import { queryKeys } from '../../lib/api/queryKeys';
import { notifyApiError } from '../../lib/api/errorToast';

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

  const renderExportMenuItems = () => (
    <>
      <DropdownMenuItem onClick={() => handleExport('json')}>Export as JSON (resolved)</DropdownMenuItem>
      <DropdownMenuItem onClick={() => handleExport('env')}>Export as .env (resolved)</DropdownMenuItem>
      <DropdownMenuItem onClick={() => handleExport('json', true)}>Export as JSON (raw)</DropdownMenuItem>
      <DropdownMenuItem onClick={() => handleExport('env', true)}>Export as .env (raw)</DropdownMenuItem>
    </>
  );

  return (
    <header className="h-12 shrink-0 border-b border-border bg-background px-2 sm:px-3 lg:px-4">
      <div className="flex h-full items-center gap-2 lg:gap-3">
        <SidebarTrigger
          className="h-8 w-8 p-0 text-muted-foreground"
          aria-label="Toggle navigation"
        />

        <Breadcrumb className="min-w-0 flex-1">
          <BreadcrumbList className="flex-nowrap overflow-hidden">
            <BreadcrumbItem className="shrink-0">
              <BreadcrumbLink asChild className="text-xs sm:text-sm">
                <Link to="/projects">Projects</Link>
              </BreadcrumbLink>
            </BreadcrumbItem>

            {projectSlug && (
              <>
                <BreadcrumbSeparator />
                <BreadcrumbItem className="min-w-0">
                  <BreadcrumbLink
                    asChild
                    className="block max-w-[8rem] truncate text-xs sm:max-w-[12rem] sm:text-sm lg:max-w-[16rem]"
                  >
                    <Link to={`/projects/${projectSlug}/settings`}>{currentProject?.name ?? projectSlug}</Link>
                  </BreadcrumbLink>
                </BreadcrumbItem>
              </>
            )}

            {configSlug && (
              <>
                <BreadcrumbSeparator />
                <BreadcrumbItem className="min-w-0">
                  <BreadcrumbPage className="max-w-[7rem] truncate font-mono text-[11px] sm:max-w-[10rem] sm:text-xs">
                    {configSlug}
                  </BreadcrumbPage>
                </BreadcrumbItem>
              </>
            )}

            {isCompareBySecretPage && (
              <>
                <BreadcrumbSeparator />
                <BreadcrumbItem className="hidden sm:inline-flex">
                  <span className="text-xs text-muted-foreground">Compare</span>
                </BreadcrumbItem>
                <BreadcrumbSeparator className="hidden sm:list-item" />
                <BreadcrumbItem>
                  <BreadcrumbPage className="text-xs">By Secret</BreadcrumbPage>
                </BreadcrumbItem>
              </>
            )}
          </BreadcrumbList>
        </Breadcrumb>

        <div className="flex shrink-0 items-center gap-1 sm:gap-2">
          {projectSlug && configs.length > 0 && (
            <div className="hidden lg:block">
              <Select value={configSlug} onValueChange={handleConfigChange}>
                <SelectTrigger className="h-8 w-36 text-xs font-mono">
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
            </div>
          )}

          {projectSlug && (
            <Button
              variant="ghost"
              size="sm"
              className="hidden h-8 w-8 p-0 text-muted-foreground lg:inline-flex"
              onClick={() => navigate(`/projects/${projectSlug}/settings`)}
              aria-label="Project settings"
            >
              <SettingsIcon className="h-3.5 w-3.5" />
            </Button>
          )}

          {projectSlug && configSlug && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" className="hidden h-8 gap-1.5 text-xs lg:inline-flex">
                  <DownloadIcon className="h-3.5 w-3.5" />
                  Export
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">{renderExportMenuItems()}</DropdownMenuContent>
            </DropdownMenu>
          )}

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0 text-muted-foreground lg:hidden"
                aria-label="Open quick actions"
              >
                <EllipsisIcon className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              {projectSlug && (
                <DropdownMenuItem onClick={() => navigate(`/projects/${projectSlug}/settings`)}>
                  <SettingsIcon className="mr-2 h-3.5 w-3.5" />
                  Project settings
                </DropdownMenuItem>
              )}

              {projectSlug && configs.length > 0 && (
                <DropdownMenuSub>
                  <DropdownMenuSubTrigger>Switch config</DropdownMenuSubTrigger>
                  <DropdownMenuSubContent className="w-48">
                    {configs.map((config) => (
                      <DropdownMenuItem key={config.slug} onClick={() => handleConfigChange(config.slug)}>
                        <span className={`font-mono text-xs ${config.slug === configSlug ? 'font-semibold' : ''}`}>
                          {config.slug}
                        </span>
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuSubContent>
                </DropdownMenuSub>
              )}

              {projectSlug && configSlug && (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuSub>
                    <DropdownMenuSubTrigger>Export</DropdownMenuSubTrigger>
                    <DropdownMenuSubContent>{renderExportMenuItems()}</DropdownMenuSubContent>
                  </DropdownMenuSub>
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}
