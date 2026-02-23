export interface ParsedEnvEntry {
  key: string;
  value: string;
}

export interface ParsedEnvResult {
  entries: ParsedEnvEntry[];
  duplicateCount: number;
  errors: string[];
}

const ENV_KEY_PATTERN = /^[A-Z0-9_]+$/;

function stripInlineComment(value: string): string {
  const commentStart = value.search(/\s#/);
  if (commentStart < 0) return value.trimEnd();
  return value.slice(0, commentStart).trimEnd();
}

function parseValue(rawValue: string): { value?: string; error?: string } {
  const trimmed = rawValue.trim();
  if (!trimmed.length) return { value: '' };

  if (trimmed.startsWith('"')) {
    if (!trimmed.endsWith('"') || trimmed.length === 1) {
      return { error: 'Unclosed double quote' };
    }
    const unquoted = trimmed.slice(1, -1);
    return {
      value: unquoted
        .replace(/\\n/g, '\n')
        .replace(/\\"/g, '"')
        .replace(/\\\\/g, '\\')
    };
  }

  if (trimmed.startsWith("'")) {
    if (!trimmed.endsWith("'") || trimmed.length === 1) {
      return { error: 'Unclosed single quote' };
    }
    return { value: trimmed.slice(1, -1).replace(/\\'/g, "'") };
  }

  return { value: stripInlineComment(rawValue) };
}

export function parseEnvContent(content: string): ParsedEnvResult {
  const keyToValue = new Map<string, string>();
  let duplicateCount = 0;
  const errors: string[] = [];
  const lines = content.split(/\r?\n/);

  lines.forEach((line, index) => {
    const lineNumber = index + 1;
    const trimmedLine = line.trim();
    if (!trimmedLine || trimmedLine.startsWith('#')) return;

    const withoutExport = trimmedLine.startsWith('export ') ?
    trimmedLine.slice('export '.length).trimStart() :
    trimmedLine;

    const separatorIndex = withoutExport.indexOf('=');
    if (separatorIndex <= 0) {
      errors.push(`Line ${lineNumber}: expected KEY=VALUE`);
      return;
    }

    const key = withoutExport.slice(0, separatorIndex).trim();
    const valuePart = withoutExport.slice(separatorIndex + 1);

    if (!ENV_KEY_PATTERN.test(key)) {
      errors.push(`Line ${lineNumber}: invalid key "${key}"`);
      return;
    }

    const parsedValue = parseValue(valuePart);
    if (parsedValue.error) {
      errors.push(`Line ${lineNumber}: ${parsedValue.error}`);
      return;
    }

    if (keyToValue.has(key)) {
      duplicateCount += 1;
    }
    keyToValue.set(key, parsedValue.value ?? '');
  });

  return {
    entries: Array.from(keyToValue.entries()).map(([key, value]) => ({ key, value })),
    duplicateCount,
    errors
  };
}
