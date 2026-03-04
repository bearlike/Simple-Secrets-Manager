export function normalizeSecretValueForSubmit(value: string): string {
  return value.trim().length === 0 ? '' : value;
}

export function requiresEmptyValueConfirmation(value: string): boolean {
  return normalizeSecretValueForSubmit(value).length === 0;
}
