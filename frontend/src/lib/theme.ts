import { useState } from 'react';

export type Theme = 'light' | 'dark';

const THEME_STORAGE_KEY = 'ssm_theme';

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
}

function getThemeFromDocument(): Theme | null {
  if (document.documentElement.classList.contains('dark')) return 'dark';
  return null;
}

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(() => getThemeFromDocument() ?? getInitialTheme());

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
