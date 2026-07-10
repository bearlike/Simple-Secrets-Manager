import { useEffect, useRef, useState } from 'react';
import { CheckIcon, ClipboardIcon } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

const COPIED_FEEDBACK_MS = 2000;

interface CopyButtonProps {
  value: string;
  label?: string;
  className?: string;
}

/**
 * Copy `value` to the clipboard, confirming with a transient "Copied" state.
 *
 * The clipboard API rejects outside a secure context (a plain-http host, a
 * denied permission). That is a best-effort side effect: say so and stop —
 * the text is on screen and still selectable either way.
 */
export function CopyButton({ value, label = 'Copy', className }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);
  const resetTimer = useRef<number>();

  useEffect(() => () => window.clearTimeout(resetTimer.current), []);

  const handleCopy = () => {
    navigator.clipboard
      .writeText(value)
      .then(() => {
        setCopied(true);
        window.clearTimeout(resetTimer.current);
        resetTimer.current = window.setTimeout(() => setCopied(false), COPIED_FEEDBACK_MS);
      })
      .catch(() => toast.error('Could not copy — select the text and copy manually'));
  };

  return (
    <Button
      variant="outline"
      size="sm"
      className={cn('shrink-0 h-7 gap-1.5', className)}
      onClick={handleCopy}
    >
      {copied ? (
        <CheckIcon className="h-3.5 w-3.5 text-green-600 dark:text-green-400" />
      ) : (
        <ClipboardIcon className="h-3.5 w-3.5" />
      )}
      {copied ? 'Copied' : label}
    </Button>
  );
}
