import { useMemo } from 'react';
import { RefreshCwIcon, ScrollTextIcon } from 'lucide-react';
import { createSearchParams, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { CopyButton } from '../common/CopyButton';
import { buildConfigSnippets, type Snippet } from '../../lib/snippets';

interface ConfigUsageDialogProps {
  projectSlug: string;
  configSlug: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function SnippetBlock({ snippet }: { snippet: Snippet }) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium">{snippet.title}</p>
          <p className="text-xs text-muted-foreground">{snippet.description}</p>
        </div>
        <CopyButton value={snippet.code} />
      </div>
      <pre className="overflow-x-auto rounded-md border border-border bg-muted p-3">
        <code className="font-mono text-xs leading-relaxed">{snippet.code}</code>
      </pre>
    </div>
  );
}

/**
 * A cheat sheet for consuming ONE project/config: the CLI, compose and
 * docker-run shapes, plus deep links into the reloader fleet and the audit log
 * already filtered to this config.
 */
export function ConfigUsageDialog({
  projectSlug,
  configSlug,
  open,
  onOpenChange
}: ConfigUsageDialogProps) {
  const navigate = useNavigate();
  const groups = useMemo(
    () => buildConfigSnippets(projectSlug, configSlug),
    [projectSlug, configSlug]
  );

  // project/config are the search-param names ReloadStatusPage and AuditPage
  // both read their filters from, so these routes land pre-scoped.
  const scopeHref = (route: string) =>
    `${route}?${createSearchParams({ project: projectSlug, config: configSlug })}`;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-3xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            Use{' '}
            <code className="font-mono">
              {projectSlug}/{configSlug}
            </code>
          </DialogTitle>
          <DialogDescription>
            Copy-ready snippets for injecting this config into a command, a compose
            stack, or a container.
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue={groups[0].id}>
          <TabsList>
            {groups.map((group) => (
              <TabsTrigger key={group.id} value={group.id}>
                {group.label}
              </TabsTrigger>
            ))}
          </TabsList>
          {groups.map((group) => (
            <TabsContent key={group.id} value={group.id} className="space-y-5 pt-3">
              {group.snippets.map((snippet) => (
                <SnippetBlock key={snippet.id} snippet={snippet} />
              ))}
            </TabsContent>
          ))}
        </Tabs>

        <DialogFooter className="gap-2 sm:justify-between">
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5"
              onClick={() => navigate(scopeHref('/reload'))}
            >
              <RefreshCwIcon className="h-3.5 w-3.5" />
              Reloader Fleet
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5"
              onClick={() => navigate(scopeHref('/audit'))}
            >
              <ScrollTextIcon className="h-3.5 w-3.5" />
              Audit Log
            </Button>
          </div>
          <Button size="sm" onClick={() => onOpenChange(false)}>
            Done
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
