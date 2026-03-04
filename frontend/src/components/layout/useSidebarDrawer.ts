import { useEffect, useState } from 'react';

const SIDEBAR_STORAGE_KEY = 'ssm_sidebar_open';

function readStoredSidebarState(): boolean | null {
  try {
    const storedValue = localStorage.getItem(SIDEBAR_STORAGE_KEY);
    if (storedValue === 'true') return true;
    if (storedValue === 'false') return false;
    return null;
  } catch {
    return null;
  }
}

export function useSidebarDrawer() {
  const [isOpen, setIsOpen] = useState<boolean>(() => readStoredSidebarState() ?? true);

  useEffect(() => {
    try {
      localStorage.setItem(SIDEBAR_STORAGE_KEY, String(isOpen));
    } catch {
      // Ignore storage failures and continue with in-memory state.
    }
  }, [isOpen]);

  return {
    isOpen,
    setIsOpen,
    toggle: () => setIsOpen((currentValue) => !currentValue)
  };
}
