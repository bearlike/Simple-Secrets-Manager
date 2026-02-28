import { toast } from 'sonner';
import { ApiClientError } from './client';

const seenErrors = new WeakSet<object>();

function fromRecord(value: unknown, key: string): string | undefined {
  if (!value || typeof value !== 'object') {
    return undefined;
  }
  const raw = (value as Record<string, unknown>)[key];
  return typeof raw === 'string' && raw.trim() ? raw.trim() : undefined;
}

export function getApiErrorMessage(error: unknown, fallback = 'Request failed'): string {
  if (error instanceof ApiClientError) {
    return error.message || fallback;
  }

  if (error instanceof Error) {
    return error.message?.trim() || fallback;
  }

  if (typeof error === 'string' && error.trim()) {
    return error.trim();
  }

  const bodyMessage = fromRecord(error, 'message') ?? fromRecord(error, 'error') ?? fromRecord(error, 'status');
  if (bodyMessage) {
    return bodyMessage;
  }

  return fallback;
}

export function notifyApiError(error: unknown, fallback = 'Request failed') {
  if (error && typeof error === 'object') {
    if (seenErrors.has(error)) {
      return;
    }
    seenErrors.add(error);
  }

  toast.error(getApiErrorMessage(error, fallback));
}
