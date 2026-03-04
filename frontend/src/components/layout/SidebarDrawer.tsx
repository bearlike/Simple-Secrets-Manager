import { Dialog, DialogContent } from '@/components/ui/dialog';

import { Sidebar } from './Sidebar';

interface SidebarDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function SidebarDrawer({ open, onOpenChange }: SidebarDrawerProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        id="app-sidebar-drawer"
        forceMount
        className="h-screen w-60 max-w-none left-0 top-0 translate-x-0 translate-y-0 rounded-none border-r border-border bg-transparent p-0 shadow-lg gap-0 [&>button]:hidden data-[state=closed]:hidden data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left data-[state=closed]:zoom-out-100 data-[state=open]:zoom-in-100"
      >
        <Sidebar ariaHidden={!open} />
      </DialogContent>
    </Dialog>
  );
}
