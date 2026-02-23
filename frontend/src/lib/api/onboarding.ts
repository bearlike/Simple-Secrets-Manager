import { ApiClientError, apiClient } from './client';

export interface OnboardingState {
  isInitialized: boolean;
  state: string;
  initializedAt?: string | null;
  initializedBy?: string | null;
}

interface OnboardingStateDto {
  isInitialized?: boolean;
  is_initialized?: boolean;
  state?: string;
  initializedAt?: string | null;
  initialized_at?: string | null;
  initializedBy?: string | null;
  initialized_by?: string | null;
}

interface OnboardingStatusResponseDto {
  status?: string;
  onboarding?: OnboardingStateDto;
}

interface OnboardingBootstrapResponseDto {
  status?: string;
  token?: string;
  expires_at?: string | null;
  onboarding?: OnboardingStateDto;
}

interface BootstrapInput {
  username: string;
  password: string;
}

interface BootstrapResult {
  token: string;
  expiresAt?: string | null;
  onboarding: OnboardingState;
}

const LEGACY_BACKEND_STATUSES = new Set([404, 405, 501]);

function asString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value : undefined;
}

function mapOnboardingState(dto: OnboardingStateDto | undefined): OnboardingState {
  const isInitialized = Boolean(dto?.isInitialized ?? dto?.is_initialized);
  return {
    isInitialized,
    state: asString(dto?.state) ?? (isInitialized ? 'completed' : 'not_initialized'),
    initializedAt: dto?.initializedAt ?? dto?.initialized_at ?? null,
    initializedBy: asString(dto?.initializedBy) ?? asString(dto?.initialized_by) ?? null
  };
}

export async function getOnboardingState(): Promise<OnboardingState> {
  try {
    const response = await apiClient<OnboardingStatusResponseDto>('/onboarding/status');
    return mapOnboardingState(response.onboarding);
  } catch (error) {
    if (error instanceof ApiClientError && LEGACY_BACKEND_STATUSES.has(error.status)) {
      return {
        isInitialized: true,
        state: 'completed',
        initializedAt: null,
        initializedBy: null
      };
    }
    throw error;
  }
}

export async function bootstrapFirstUser(input: BootstrapInput): Promise<BootstrapResult> {
  const response = await apiClient<OnboardingBootstrapResponseDto>('/onboarding/bootstrap', {
    method: 'POST',
    body: JSON.stringify(input)
  });
  const token = asString(response.token);
  if (!token) {
    throw new Error('Bootstrap succeeded but token was not returned');
  }
  return {
    token,
    expiresAt: response.expires_at ?? null,
    onboarding: mapOnboardingState(response.onboarding)
  };
}
