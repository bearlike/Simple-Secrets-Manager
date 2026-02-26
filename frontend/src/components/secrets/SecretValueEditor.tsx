import { useMemo, type KeyboardEventHandler } from 'react';
import CodeMirror from '@uiw/react-codemirror';
import { autocompletion, type Completion, type CompletionContext } from '@codemirror/autocomplete';
import { RangeSetBuilder } from '@codemirror/state';
import { Decoration, EditorView, ViewPlugin, type ViewUpdate } from '@codemirror/view';
import { cn } from '@/lib/utils';
import { highlightSecretValueHtml, isValidSecretReferenceBody } from '../../lib/secretReferences';
import { useTheme } from '../../lib/theme';

interface SecretValueEditorProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  rows?: number;
  className?: string;
  autoFocus?: boolean;
  readOnly?: boolean;
  onKeyDown?: KeyboardEventHandler<HTMLTextAreaElement>;
  autocompleteItems?: string[];
}

const SECRET_REFERENCE_PATTERN = /\$\{([^{}]+)\}/g;
const VALID_DECORATION = Decoration.mark({ class: 'cm-ssm-ref-valid' });
const INVALID_DECORATION = Decoration.mark({ class: 'cm-ssm-ref-invalid' });

function buildReferenceDecorations(view: EditorView) {
  const builder = new RangeSetBuilder<Decoration>();
  const value = view.state.doc.toString();
  for (const match of value.matchAll(SECRET_REFERENCE_PATTERN)) {
    const token = match[0];
    const body = match[1];
    const start = match.index ?? 0;
    const end = start + token.length;
    builder.add(start, end, isValidSecretReferenceBody(body) ? VALID_DECORATION : INVALID_DECORATION);
  }
  return builder.finish();
}

const referenceHighlightPlugin = ViewPlugin.fromClass(
  class {
    decorations;

    constructor(view: EditorView) {
      this.decorations = buildReferenceDecorations(view);
    }

    update(update: ViewUpdate) {
      if (update.docChanged || update.viewportChanged) {
        this.decorations = buildReferenceDecorations(update.view);
      }
    }
  },
  {
    decorations: (instance) => instance.decorations
  }
);

function createReferenceCompletionSource(items: string[]) {
  const options: Completion[] = Array.from(new Set(items)).map((label) => ({
    label,
    type: 'variable'
  }));
  return (context: CompletionContext) => {
    if (options.length === 0) return null;

    const beforeCursor = context.state.sliceDoc(0, context.pos);
    const markerIndex = beforeCursor.lastIndexOf('${');
    if (markerIndex < 0) return null;

    const closingIndex = beforeCursor.slice(markerIndex).indexOf('}');
    if (closingIndex >= 0) return null;

    const current = beforeCursor.slice(markerIndex + 2);
    if (!/^[A-Za-z0-9_.-]*$/.test(current)) return null;

    const filtered = options
      .filter((option) => option.label.toLowerCase().startsWith(current.toLowerCase()))
      .slice(0, 100);

    if (!filtered.length && !context.explicit) return null;

    return {
      from: markerIndex + 2,
      options: filtered.length ? filtered : options.slice(0, 20),
      validFor: /^[A-Za-z0-9_.-]*$/
    };
  };
}

function createEditorTheme(isDark: boolean) {
  return EditorView.theme(
    {
      '&': {
        minHeight: '100%'
      },
      '.cm-editor': {
        minHeight: '100%',
        backgroundColor: 'hsl(var(--background))',
        color: 'hsl(var(--foreground))'
      },
      '.cm-scroller': {
        minHeight: '100%',
        backgroundColor: 'hsl(var(--background))',
        color: 'hsl(var(--foreground))',
        fontFamily:
          'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
        lineHeight: '1.5'
      },
      '.cm-gutters': {
        backgroundColor: 'hsl(var(--background))',
        color: 'hsl(var(--muted-foreground))',
        border: 'none'
      },
      '.cm-content': {
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        padding: '0.5rem 0.625rem'
      },
      '.cm-line': {
        overflowWrap: 'anywhere'
      },
      '.cm-activeLine': {
        backgroundColor: 'hsl(var(--accent) / 0.65)'
      },
      '.cm-selectionBackground, &.cm-focused .cm-selectionBackground, ::selection': {
        backgroundColor: isDark ? 'hsl(216 34% 22%)' : 'hsl(215 20% 86%)'
      },
      '.cm-cursor, .cm-dropCursor': {
        borderLeftColor: 'hsl(var(--foreground))'
      },
      '.cm-tooltip': {
        backgroundColor: 'hsl(var(--popover))',
        color: 'hsl(var(--popover-foreground))',
        border: '1px solid hsl(var(--border))'
      },
      '.cm-tooltip-autocomplete ul li[aria-selected]': {
        backgroundColor: 'hsl(var(--accent))',
        color: 'hsl(var(--accent-foreground))'
      },
      '&.cm-focused': {
        outline: 'none'
      }
    },
    { dark: isDark }
  );
}

export function SecretValueEditor({
  value,
  onChange,
  placeholder,
  rows = 3,
  className,
  autoFocus = false,
  readOnly = false,
  onKeyDown,
  autocompleteItems = []
}: SecretValueEditorProps) {
  const { theme } = useTheme();
  const minHeight = `${Math.max(rows, 3) * 24}px`;
  const completionSource = createReferenceCompletionSource(autocompleteItems);
  const isDark = theme === 'dark';
  const editorTheme = useMemo(() => createEditorTheme(isDark), [isDark]);

  return (
    <CodeMirror
      value={value}
      onChange={(next) => onChange(next)}
      className={cn('ssm-secret-editor-cm rounded-md border border-input bg-background shadow-sm', className)}
      style={{ minHeight }}
      placeholder={placeholder}
      editable={!readOnly}
      autoFocus={autoFocus}
      onKeyDown={onKeyDown}
      theme={isDark ? 'dark' : 'light'}
      basicSetup={{
        lineNumbers: false,
        foldGutter: false,
        highlightActiveLineGutter: false,
        highlightActiveLine: false
      }}
      extensions={[
        editorTheme,
        referenceHighlightPlugin,
        EditorView.lineWrapping,
        autocompletion({
          override: [completionSource]
        })
      ]}
    />
  );
}

interface SecretValueTextProps {
  value: string;
  className?: string;
}

export function SecretValueText({ value, className }: SecretValueTextProps) {
  if (value.length === 0) {
    return (
      <span
        className={cn(
          'ssm-secret-value block max-w-full font-mono text-sm italic text-muted-foreground/80',
          className
        )}
      >
        Empty Value
      </span>
    );
  }

  return (
    <span
      className={cn(
        'ssm-secret-value block max-w-full whitespace-pre-wrap break-words font-mono text-sm text-muted-foreground',
        className
      )}
      dangerouslySetInnerHTML={{ __html: highlightSecretValueHtml(value) }}
    />
  );
}
