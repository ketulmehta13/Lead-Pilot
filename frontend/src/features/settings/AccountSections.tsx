import type { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { Moon, Sun } from 'lucide-react';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { accountApi } from '../../api/auth';
import { useToast } from '../../components/Toast';
import { Button } from '../../components/ui/Button';
import { TextField } from '../../components/ui/Field';
import { Badge } from '../../components/ui/misc';
import { type Theme, useTheme } from '../../hooks/useTheme';
import { applyServerErrors } from '../../lib/forms';
import { ROLE_TONE, roleLabel } from '../../lib/options';
import { changePasswordSchema, profileSchema } from '../../lib/schemas';
import { useAuth } from '../auth/AuthContext';
import { SettingsSection } from './SettingsSection';

type ProfileValues = z.infer<typeof profileSchema>;
const PROFILE_FIELDS = ['first_name', 'last_name', 'email'] as const;

export function ProfileSection() {
  const { user, updateUser } = useAuth();
  const toast = useToast();
  const { register, handleSubmit, reset, setError, formState } = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: { first_name: '', last_name: '', email: '' },
  });

  useEffect(() => {
    if (user) reset({ first_name: user.first_name, last_name: user.last_name, email: user.email });
  }, [user, reset]);

  const mutation = useMutation({
    mutationFn: (v: ProfileValues) => accountApi.updateMe(v),
    onSuccess: (saved) => {
      updateUser(saved);
      toast.success('Profile saved');
    },
    onError: (err) => toast.error(applyServerErrors(err, setError, PROFILE_FIELDS)),
  });

  if (!user) return null;
  const e = formState.errors;
  return (
    <SettingsSection
      id="profile"
      title="Profile"
      description="Your name and email as your team sees them."
    >
      <dl className="mb-4 flex flex-wrap gap-x-8 gap-y-2 text-sm">
        <div>
          <dt className="text-slate-500">Username</dt>
          <dd className="font-medium">{user.username}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Role</dt>
          <dd>
            <Badge tone={ROLE_TONE[user.role]}>{roleLabel(user.role)}</Badge>
          </dd>
        </div>
      </dl>
      <form
        noValidate
        onSubmit={handleSubmit((v) => mutation.mutate(v))}
        className="grid gap-4 sm:grid-cols-2"
      >
        <TextField
          label="First name"
          autoComplete="given-name"
          error={e.first_name?.message}
          {...register('first_name')}
        />
        <TextField
          label="Last name"
          autoComplete="family-name"
          error={e.last_name?.message}
          {...register('last_name')}
        />
        <div className="sm:col-span-2">
          <TextField
            label="Email"
            type="email"
            required
            autoComplete="email"
            error={e.email?.message}
            {...register('email')}
          />
        </div>
        <div className="sm:col-span-2">
          <Button type="submit" loading={mutation.isPending} disabled={!formState.isDirty}>
            Save profile
          </Button>
        </div>
      </form>
    </SettingsSection>
  );
}

type PasswordValues = z.infer<typeof changePasswordSchema>;
const PASSWORD_FIELDS = ['current_password', 'new_password'] as const;
const emptyPassword: PasswordValues = { current_password: '', new_password: '', confirm: '' };

export function PasswordSection() {
  const toast = useToast();
  const { register, handleSubmit, reset, setError, formState } = useForm<PasswordValues>({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: emptyPassword,
  });

  const mutation = useMutation({
    mutationFn: (v: PasswordValues) =>
      accountApi.changePassword(v.current_password, v.new_password),
    onSuccess: () => {
      reset(emptyPassword);
      toast.success('Password changed');
    },
    onError: (err) => toast.error(applyServerErrors(err, setError, PASSWORD_FIELDS)),
  });

  const e = formState.errors;
  return (
    <SettingsSection
      id="password"
      title="Password"
      description="At least 8 characters, not only numbers, and not too common."
    >
      <form
        noValidate
        onSubmit={handleSubmit((v) => mutation.mutate(v))}
        className="grid gap-4 sm:grid-cols-3"
      >
        <TextField
          label="Current password"
          type="password"
          required
          autoComplete="current-password"
          error={e.current_password?.message}
          {...register('current_password')}
        />
        <TextField
          label="New password"
          type="password"
          required
          autoComplete="new-password"
          error={e.new_password?.message}
          {...register('new_password')}
        />
        <TextField
          label="Confirm new password"
          type="password"
          required
          autoComplete="new-password"
          error={e.confirm?.message}
          {...register('confirm')}
        />
        <div className="sm:col-span-3">
          <Button type="submit" loading={mutation.isPending}>
            Change password
          </Button>
        </div>
      </form>
    </SettingsSection>
  );
}

const THEMES: { value: Theme; label: string; Icon: typeof Sun }[] = [
  { value: 'light', label: 'Light', Icon: Sun },
  { value: 'dark', label: 'Dark', Icon: Moon },
];

export function AppearanceSection() {
  const { theme, setTheme } = useTheme();
  return (
    <SettingsSection
      id="appearance"
      title="Appearance"
      description="Saved on this device. The moon/sun button in the top bar switches it too."
    >
      <div role="radiogroup" aria-label="Theme" className="flex flex-wrap gap-3">
        {THEMES.map(({ value, label, Icon }) => {
          const active = theme === value;
          return (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => setTheme(value)}
              className={`flex w-36 items-center gap-2 rounded-lg border px-3 py-2.5 text-sm font-medium transition-colors ${
                active
                  ? 'border-indigo-500 bg-indigo-50 text-indigo-700 ring-2 ring-indigo-500/20 dark:bg-indigo-500/15 dark:text-indigo-300'
                  : 'border-slate-300 text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800'
              }`}
            >
              <Icon className="size-4" aria-hidden />
              {label}
            </button>
          );
        })}
      </div>
    </SettingsSection>
  );
}
