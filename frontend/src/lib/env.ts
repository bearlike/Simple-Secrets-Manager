export interface ParsedEnvEntry {
  key: string;
  value: string;
  hasReference: boolean;
}

export interface ParsedEnvResult {
  entries: ParsedEnvEntry[];
  duplicateCount: number;
  errors: string[];
}

const ENV_KEY_PATTERN = /^[A-Za-z_][A-Za-z0-9_]*$/;
const SECRET_REFERENCE_PATTERN = /\$\{[^{}]+\}/;

export function containsSecretReference(value: string): boolean {
  return SECRET_REFERENCE_PATTERN.test(value);
}

function stripInlineComment(value: string): string {
  const commentStart = value.search(/\s#/);
  if (commentStart < 0) return value.trimEnd();
  return value.slice(0, commentStart).trimEnd();
}

function findClosingQuoteIndex(value: string, quote: '"' | "'"): number {
  let escaped = false;
  for (let i = 0; i < value.length; i += 1) {
    const char = value[i];
    if (escaped) {
      escaped = false;
      continue;
    }
    if (char === '\\') {
      escaped = true;
      continue;
    }
    if (char === quote) {
      return i;
    }
  }
  return -1;
}

function decodeDoubleQuotedValue(input: string): string {
  let output = '';
  for (let i = 0; i < input.length; i += 1) {
    const char = input[i];
    if (char !== '\\' || i + 1 >= input.length) {
      output += char;
      continue;
    }

    const next = input[i + 1];
    i += 1;
    switch (next) {
      case 'n':
        output += '\n';
        break;
      case 'r':
        output += '\r';
        break;
      case 't':
        output += '\t';
        break;
      case '"':
        output += '"';
        break;
      case '\\':
        output += '\\';
        break;
      default:
        output += next;
        break;
    }
  }
  return output;
}

function decodeSingleQuotedValue(input: string): string {
  let output = '';
  for (let i = 0; i < input.length; i += 1) {
    const char = input[i];
    if (char !== '\\' || i + 1 >= input.length) {
      output += char;
      continue;
    }

    const next = input[i + 1];
    if (next === "'" || next === '\\') {
      output += next;
      i += 1;
      continue;
    }
    output += '\\';
  }
  return output;
}

function parseQuotedValue(
  quote: '"' | "'",
  valuePart: string,
  lines: string[],
  startIndex: number
): { value?: string; error?: string; consumedLines: number } {
  let content = valuePart.trimStart().slice(1);
  let consumedLines = 0;
  let collected = '';

  for (;;) {
    const closingIndex = findClosingQuoteIndex(content, quote);
    if (closingIndex >= 0) {
      collected += content.slice(0, closingIndex);
      const trailing = content.slice(closingIndex + 1).trimStart();
      if (trailing.length > 0 && !trailing.startsWith('#')) {
        return { error: `Unexpected content after closing ${quote} quote`, consumedLines };
      }

      return {
        value: quote === '"' ? decodeDoubleQuotedValue(collected) : decodeSingleQuotedValue(collected),
        consumedLines
      };
    }

    collected += content;
    const nextLineIndex = startIndex + consumedLines + 1;
    if (nextLineIndex >= lines.length) {
      return { error: quote === '"' ? 'Unclosed double quote' : 'Unclosed single quote', consumedLines };
    }

    collected += '\n';
    consumedLines += 1;
    content = lines[nextLineIndex];
  }
}

function parseValue(
  rawValue: string,
  lines: string[],
  startIndex: number
): { value?: string; error?: string; consumedLines: number } {
  const trimmed = rawValue.trimStart();
  if (!trimmed.length) return { value: '', consumedLines: 0 };

  if (trimmed.startsWith('"')) {
    return parseQuotedValue('"', rawValue, lines, startIndex);
  }

  if (trimmed.startsWith("'")) {
    return parseQuotedValue("'", rawValue, lines, startIndex);
  }

  return { value: stripInlineComment(trimmed), consumedLines: 0 };
}

export function parseEnvContent(content: string): ParsedEnvResult {
  const keyToValue = new Map<string, string>();
  let duplicateCount = 0;
  const errors: string[] = [];
  const lines = content.split(/\r?\n/);

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const lineNumber = index + 1;
    const trimmedLine = line.trim();
    if (!trimmedLine || trimmedLine.startsWith('#')) continue;

    const withoutExport = trimmedLine.startsWith('export ') ?
    trimmedLine.slice('export '.length).trimStart() :
    trimmedLine;

    const separatorIndex = withoutExport.indexOf('=');
    if (separatorIndex <= 0) {
      errors.push(`Line ${lineNumber}: expected KEY=VALUE`);
      continue;
    }

    const key = withoutExport.slice(0, separatorIndex).trim();
    const valuePart = withoutExport.slice(separatorIndex + 1);

    if (!ENV_KEY_PATTERN.test(key)) {
      errors.push(`Line ${lineNumber}: invalid key "${key}"`);
      continue;
    }

    const parsedValue = parseValue(valuePart, lines, index);
    if (parsedValue.error) {
      errors.push(`Line ${lineNumber}: ${parsedValue.error}`);
      continue;
    }

    if (keyToValue.has(key)) {
      duplicateCount += 1;
    }
    keyToValue.set(key, parsedValue.value ?? '');

    if (parsedValue.consumedLines > 0) {
      index += parsedValue.consumedLines;
    }
  }

  return {
    entries: Array.from(keyToValue.entries()).map(([key, value]) => ({
      key,
      value,
      hasReference: containsSecretReference(value)
    })),
    duplicateCount,
    errors
  };
}
