import type { LucideIcon } from 'lucide-react';

export interface SecretRowAction {
  key: string;
  label: string;
  onSelect: () => void;
  icon: LucideIcon;
  destructive?: boolean;
  disabled?: boolean;
}
