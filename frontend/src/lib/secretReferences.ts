import Prism from 'prismjs';

const SECRET_REFERENCE_PATTERN = /\$\{[^{}]+\}/;
const LOCAL_KEY_PATTERN = /^[A-Z0-9_]+$/;
const SLUG_PATTERN = /^[a-z0-9_-]+$/;

const secretReferenceGrammar: Prism.Grammar = {
  reference_project: {
    pattern: /\$\{[a-z0-9_-]+\.[a-z0-9_-]+\.[A-Z0-9_]+\}/,
    alias: 'ssm-ref-token-valid'
  },
  reference_config: {
    pattern: /\$\{[a-z0-9_-]+\.[A-Z0-9_]+\}/,
    alias: 'ssm-ref-token-valid'
  },
  reference_local: {
    pattern: /\$\{[A-Z0-9_]+\}/,
    alias: 'ssm-ref-token-valid'
  },
  reference_invalid: {
    pattern: /\$\{[^{}]+\}/,
    alias: 'ssm-ref-token-invalid'
  }
};

export function containsSecretReference(value: string): boolean {
  return SECRET_REFERENCE_PATTERN.test(value);
}

export function highlightSecretValueHtml(value: string): string {
  return Prism.highlight(value, secretReferenceGrammar, 'ssm-secret-value');
}

export function isValidSecretReferenceBody(referenceBody: string): boolean {
  const parts = referenceBody.split('.');
  if (parts.length === 1) {
    return LOCAL_KEY_PATTERN.test(parts[0]);
  }
  if (parts.length === 2) {
    return SLUG_PATTERN.test(parts[0]) && LOCAL_KEY_PATTERN.test(parts[1]);
  }
  if (parts.length === 3) {
    return SLUG_PATTERN.test(parts[0]) && SLUG_PATTERN.test(parts[1]) && LOCAL_KEY_PATTERN.test(parts[2]);
  }
  return false;
}
