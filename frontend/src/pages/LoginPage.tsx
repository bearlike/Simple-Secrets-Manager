import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Navigate, useNavigate } from 'react-router-dom';
import { LockIcon } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from '@/components/ui/card';
import { useAuth } from '../lib/auth';
import { queryKeys } from '../lib/api/queryKeys';
import { bootstrapFirstUser, getOnboardingState } from '../lib/api/onboarding';

const tokenSchema = z.object({
  token: z.string().min(10, 'Token must be at least 10 characters')
});

const setupSchema = z
  .object({
    username: z
      .string()
      .min(2, 'Username is required')
      .regex(/^[a-zA-Z0-9_]+$/, 'Use letters, numbers, or underscore'),
    password: z.string().min(8, 'Password must be at least 8 characters'),
    confirmPassword: z.string().min(8, 'Confirm your password')
  })
  .refine((value) => value.password === value.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword']
  });

type TokenFormValues = z.infer<typeof tokenSchema>;
type SetupFormValues = z.infer<typeof setupSchema>;

export function LoginPage() {
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const tokenForm = useForm<TokenFormValues>({
    resolver: zodResolver(tokenSchema)
  });
  const setupForm = useForm<SetupFormValues>({
    resolver: zodResolver(setupSchema)
  });

  const onboardingQuery = useQuery({
    queryKey: queryKeys.onboardingStatus(),
    queryFn: getOnboardingState,
    retry: false
  });

  const bootstrapMutation = useMutation({
    mutationFn: ({ username, password }: { username: string; password: string }) =>
      bootstrapFirstUser({ username, password }),
    onSuccess: (result) => {
      login(result.token);
      toast.success('Initial administrator created');
      navigate('/projects');
    },
    onError: (error) => {
      if (error instanceof Error) {
        toast.error(error.message);
      } else {
        toast.error('Failed to initialize the system');
      }
    }
  });

  const {
    register,
    handleSubmit,
    formState: { errors }
  } = tokenForm;

  if (isAuthenticated) {
    return <Navigate to="/projects" replace />;
  }

  const onSubmitToken = ({ token }: TokenFormValues) => {
    login(token);
    navigate('/projects');
  };

  const onSubmitSetup = ({ username, password }: SetupFormValues) => {
    bootstrapMutation.mutate({ username, password });
  };

  const showSetupWizard = onboardingQuery.data ? !onboardingQuery.data.isInitialized : false;

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-muted/20">
      <div className="w-full max-w-sm px-4">
        <div className="flex flex-col items-center mb-8">
          <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-primary mb-4">
            <LockIcon className="h-5 w-5 text-primary-foreground" />
          </div>
          <h1 className="text-xl font-semibold">Simple Secrets Manager</h1>
          <p className="text-sm text-muted-foreground mt-1">Secure secrets for your team</p>
        </div>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">{showSetupWizard ? 'Initial Setup' : 'Sign In'}</CardTitle>
            <CardDescription className="text-sm">
              {showSetupWizard ?
              'Create the first administrator and bootstrap token' :
              'Enter your personal access token to continue'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {onboardingQuery.isLoading ?
            <p className="text-sm text-muted-foreground">Checking system initialization status...</p> :
            showSetupWizard ?
            <form onSubmit={setupForm.handleSubmit(onSubmitSetup)} className="space-y-4">
                <div className="space-y-1.5">
                  <Label htmlFor="username">Admin Username</Label>
                  <Input
                    id="username"
                    type="text"
                    {...setupForm.register('username')}
                    placeholder="admin"
                    autoComplete="username"
                    autoFocus
                  />
                  {setupForm.formState.errors.username &&
                <p className="text-xs text-destructive">{setupForm.formState.errors.username.message}</p>
                }
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="password">Admin Password</Label>
                  <Input
                    id="password"
                    type="password"
                    {...setupForm.register('password')}
                    autoComplete="new-password"
                  />
                  {setupForm.formState.errors.password &&
                <p className="text-xs text-destructive">{setupForm.formState.errors.password.message}</p>
                }
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="confirmPassword">Confirm Password</Label>
                  <Input
                    id="confirmPassword"
                    type="password"
                    {...setupForm.register('confirmPassword')}
                    autoComplete="new-password"
                  />
                  {setupForm.formState.errors.confirmPassword &&
                <p className="text-xs text-destructive">
                      {setupForm.formState.errors.confirmPassword.message}
                    </p>
                }
                </div>
                <Button type="submit" className="w-full" disabled={bootstrapMutation.isPending}>
                  {bootstrapMutation.isPending ? 'Initializing...' : 'Initialize System'}
                </Button>
              </form> :
            <form onSubmit={handleSubmit(onSubmitToken)} className="space-y-4">
                <div className="space-y-1.5">
                  <Label htmlFor="token">API Token</Label>
                  <Input
                    id="token"
                    type="password"
                    {...register('token')}
                    placeholder="dp.st.••••••••••••••••"
                    className="font-mono text-sm"
                    autoComplete="current-password"
                    autoFocus
                  />
                  {errors.token && <p className="text-xs text-destructive">{errors.token.message}</p>}
                </div>
                <Button type="submit" className="w-full">
                  Sign In
                </Button>
              </form>
            }
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
