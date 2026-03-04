import { Outlet } from 'react-router-dom';
import { SidebarDrawer } from './SidebarDrawer';
import { TopBar } from './TopBar';

import { useSidebarDrawer } from './useSidebarDrawer';

export function AppShell() {
  const { isOpen, setIsOpen, toggle } = useSidebarDrawer();

  return (
    <div className="h-screen overflow-hidden bg-background">
      <SidebarDrawer open={isOpen} onOpenChange={setIsOpen} />
      <div className="flex h-full flex-col overflow-hidden">
        <TopBar isSidebarOpen={isOpen} onMenuToggle={toggle} />
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
