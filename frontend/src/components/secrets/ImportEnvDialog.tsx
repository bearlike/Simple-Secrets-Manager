import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

export type EnvImportAction = 'create' | 'overwrite' | 'override_inherited';

export interface EnvImportPreviewItem {
  key: string;
  value: string;
  action: EnvImportAction;
  hasReference: boolean;
}

export interface EnvImportPreview {
  fileName: string;
  total: number;
  duplicateCount: number;
  createCount: number;
  overwriteCount: number;
  overrideInheritedCount: number;
  items: EnvImportPreviewItem[];
}

interface ImportEnvDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  preview: EnvImportPreview | null;
  loading: boolean;
  onConfirm: () => void;
}

function actionLabel(action: EnvImportAction): string {
  if (action === 'create') return 'New';
  if (action === 'overwrite') return 'Overwrite';
  return 'Override inherited';
}

function actionBadgeClass(action: EnvImportAction): string {
  if (action === 'create') {
    return 'bg-green-50 text-green-700 border-green-200 dark:bg-green-950 dark:text-green-300 dark:border-green-800';
  }
  if (action === 'overwrite') {
    return 'bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-950 dark:text-orange-300 dark:border-orange-800';
  }
  return 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-300 dark:border-blue-800';
}

export function ImportEnvDialog({ open, onOpenChange, preview, loading, onConfirm }: ImportEnvDialogProps) {
  if (!preview) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[640px]">
        <DialogHeader>
          <DialogTitle>Import .env File</DialogTitle>
          <DialogDescription>
            Review changes from <span className="font-mono text-xs">{preview.fileName}</span> before applying.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline" className="text-xs">
              Total: {preview.total}
            </Badge>
            <Badge variant="outline" className="text-xs">
              New: {preview.createCount}
            </Badge>
            <Badge variant="outline" className="text-xs">
              Overwrite: {preview.overwriteCount}
            </Badge>
            <Badge variant="outline" className="text-xs">
              Override inherited: {preview.overrideInheritedCount}
            </Badge>
            {preview.duplicateCount > 0 &&
              <Badge variant="outline" className="text-xs">
                Duplicates resolved: {preview.duplicateCount}
              </Badge>
            }
          </div>

          <div className="max-h-64 overflow-y-auto rounded-md border border-border">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-muted/40 border-b border-border">
                  <th className="px-3 py-2 text-left text-xs font-medium tracking-wider text-muted-foreground">
                    KEY
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium tracking-wider text-muted-foreground">
                    ACTION
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium tracking-wider text-muted-foreground">
                    TYPE
                  </th>
                </tr>
              </thead>
              <tbody>
                {preview.items.map((item) =>
                  <tr key={item.key} className="border-b border-border last:border-0">
                    <td className="px-3 py-2">
                      <code className="font-mono text-xs">{item.key}</code>
                    </td>
                    <td className="px-3 py-2">
                      <Badge variant="outline" className={`text-xs ${actionBadgeClass(item.action)}`}>
                        {actionLabel(item.action)}
                      </Badge>
                    </td>
                    <td className="px-3 py-2">
                      {item.hasReference ?
                      <Badge variant="outline" className="text-xs">
                          Uses references
                        </Badge> :
                      <span className="text-xs text-muted-foreground">Literal</span>
                      }
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={loading}>
            Cancel
          </Button>
          <Button onClick={onConfirm} disabled={loading}>
            {loading ? 'Importing...' : `Import ${preview.total} variables`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
