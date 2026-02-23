import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Navigate, useNavigate } from 'react-router-dom';
import { LockIcon } from 'lucide-react';
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

const schema = z.object({
  token: z.string().min(10, 'Token must be at least 10 characters')
});

type FormValues = z.infer<typeof schema>;

export function LoginPage() {
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const {
    register,
    handleSubmit,
    formState: { errors }
  } = useForm<FormValues>({
    resolver: zodResolver(schema)
  });

  if (isAuthenticated) {
    return <Navigate to="/projects" replace />;
  }

  const onSubmit = ({ token }: FormValues) => {
    login(token);
    navigate('/projects');
  };

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
            <CardTitle className="text-base">Sign In</CardTitle>
            <CardDescription className="text-sm">
              Enter your personal access token to continue
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
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
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
