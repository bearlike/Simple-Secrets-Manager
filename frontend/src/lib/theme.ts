import { useEffect, useState } from 'react';

export type Theme = 'light' | 'dark';

const THEME_STORAGE_KEY = 'ssm_theme';
const THEME_EVENT_NAME = 'ssm:theme-change';

function isTheme(value: string | null): value is Theme {
  return value === 'light' || value === 'dark';
}

function getSystemTheme(): Theme {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return 'light';
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function getStoredTheme(): Theme | null {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    return isTheme(stored) ? stored : null;
  } catch {
    return null;
  }
}

export function getInitialTheme(): Theme {
  return getStoredTheme() ?? getSystemTheme();
}

export function applyTheme(theme: Theme): void {
  document.documentElement.classList.toggle('dark', theme === 'dark');
  document.documentElement.style.colorScheme = theme;
}

export function setTheme(theme: Theme): void {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // Ignore storage errors and still apply the theme in-memory.
  }
  applyTheme(theme);
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent<Theme>(THEME_EVENT_NAME, { detail: theme }));
  }
}

function getThemeFromDocument(): Theme | null {
  if (document.documentElement.classList.contains('dark')) return 'dark';
  return null;
}

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(() => getThemeFromDocument() ?? getInitialTheme());

  useEffect(() => {
    const handleThemeChange = (event: Event) => {
      const customEvent = event as CustomEvent<Theme>;
      if (isTheme(customEvent.detail)) {
        setThemeState(customEvent.detail);
        return;
      }
      setThemeState(getThemeFromDocument() ?? getInitialTheme());
    };

    const handleStorage = (event: StorageEvent) => {
      if (event.key !== THEME_STORAGE_KEY) return;
      setThemeState(getThemeFromDocument() ?? getInitialTheme());
    };

    window.addEventListener(THEME_EVENT_NAME, handleThemeChange as EventListener);
    window.addEventListener('storage', handleStorage);
    return () => {
      window.removeEventListener(THEME_EVENT_NAME, handleThemeChange as EventListener);
      window.removeEventListener('storage', handleStorage);
    };
  }, []);

  const updateTheme = (nextTheme: Theme) => {
    setThemeState(nextTheme);
    setTheme(nextTheme);
  };

  const toggleTheme = () => {
    updateTheme(theme === 'dark' ? 'light' : 'dark');
  };

  return {
    theme,
    setTheme: updateTheme,
    toggleTheme
  };
}
