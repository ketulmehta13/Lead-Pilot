import type { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { usersApi } from '../../api/auth';
import { useToast } from '../../components/Toast';
import { Button } from '../../components/ui/Button';
import { SelectField, TextField } from '../../components/ui/Field';
import { Modal } from '../../components/ui/Modal';
import { applyServerErrors } from '../../lib/forms';
import { ROLE_OPTIONS } from '../../lib/options';
import { newTeamMemberSchema, resetPasswordSchema, teamMemberSchema } from '../../lib/schemas';
import type { User } from '../../types';

type MemberValues = z.infer<typeof teamMemberSchema>;
const MEMBER_FIELDS = ['username', 'first_name', 'last_name', 'email', 'role', 'password'] as const;
const emptyMember: MemberValues = {
  username: '',
  first_name: '',
  last_name: '',
  email: '',
  role: 'sales',
  password: '',
};

/** Add a team member, or edit one (name, email, role). Passwords are reset separately. */
export function TeamMemberModal({
  open,
  member,
  isSelf,
  onClose,
}: {
  open: boolean;
  member: User | null;
  isSelf: boolean;
  onClose: () => void;
}) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const editing = Boolean(member);
  const { register, handleSubmit, reset, setError, formState } = useForm<MemberValues>({
    resolver: zodResolver(editing ? teamMemberSchema : newTeamMemberSchema),
    defaultValues: emptyMember,
  });

  useEffect(() => {
    if (!open) return;
    reset(
      member
        ? {
            username: member.username,
            first_name: member.first_name,
            last_name: member.last_name,
            email: member.email,
            role: member.role,
            password: '',
          }
        : emptyMember,
    );
  }, [open, member, reset]);

  const mutation = useMutation({
    mutationFn: (v: MemberValues) => {
      if (member) {
        const { first_name, last_name, email, role } = v;
        return usersApi.update(member.id, { first_name, last_name, email, role });
      }
      return usersApi.create(v);
    },
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: [usersApi.key] });
      toast.success(member ? 'Team member updated' : `Added ${saved.full_name}`);
      onClose();
    },
    onError: (err) => toast.error(applyServerErrors(err, setError, MEMBER_FIELDS)),
  });

  const e = formState.errors;
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={member ? `Edit ${member.full_name}` : 'Add team member'}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="member-form" loading={mutation.isPending}>
            {member ? 'Save changes' : 'Add member'}
          </Button>
        </>
      }
    >
      <form
        id="member-form"
        noValidate
        onSubmit={handleSubmit((v) => mutation.mutate(v))}
        className="grid gap-4 sm:grid-cols-2"
      >
        <TextField
          label="Username"
          required
          disabled={editing}
          hint={editing ? 'Usernames can’t be changed.' : 'Used to sign in.'}
          autoComplete="off"
          error={e.username?.message}
          {...register('username')}
        />
        <SelectField
          label="Role"
          options={ROLE_OPTIONS}
          disabled={isSelf}
          hint={isSelf ? 'You can’t change your own role.' : undefined}
          error={e.role?.message}
          {...register('role')}
        />
        <TextField label="First name" error={e.first_name?.message} {...register('first_name')} />
        <TextField label="Last name" error={e.last_name?.message} {...register('last_name')} />
        <div className="sm:col-span-2">
          <TextField
            label="Email"
            type="email"
            required
            error={e.email?.message}
            {...register('email')}
          />
        </div>
        {!editing && (
          <div className="sm:col-span-2">
            <TextField
              label="Temporary password"
              type="password"
              required
              autoComplete="new-password"
              hint="Share it privately; they can change it in Settings."
              error={e.password?.message}
              {...register('password')}
            />
          </div>
        )}
      </form>
    </Modal>
  );
}

type ResetValues = z.infer<typeof resetPasswordSchema>;

/** An admin sets a new password for a team member who forgot theirs. */
export function ResetPasswordModal({
  member,
  onClose,
}: {
  member: User | null;
  onClose: () => void;
}) {
  const toast = useToast();
  const { register, handleSubmit, reset, setError, formState } = useForm<ResetValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { password: '', confirm: '' },
  });

  useEffect(() => {
    if (member) reset({ password: '', confirm: '' });
  }, [member, reset]);

  const mutation = useMutation({
    mutationFn: (v: ResetValues) => usersApi.setPassword(member!.id, v.password),
    onSuccess: () => {
      toast.success(`Password reset for ${member?.full_name}`);
      onClose();
    },
    onError: (err) => toast.error(applyServerErrors(err, setError, ['password'])),
  });

  const e = formState.errors;
  return (
    <Modal
      open={Boolean(member)}
      onClose={onClose}
      title={`Reset password for ${member?.full_name ?? ''}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="reset-form" loading={mutation.isPending}>
            Reset password
          </Button>
        </>
      }
    >
      <form
        id="reset-form"
        noValidate
        onSubmit={handleSubmit((v) => mutation.mutate(v))}
        className="grid gap-4"
      >
        <TextField
          label="New password"
          type="password"
          required
          autoComplete="new-password"
          error={e.password?.message}
          {...register('password')}
        />
        <TextField
          label="Confirm new password"
          type="password"
          required
          autoComplete="new-password"
          error={e.confirm?.message}
          {...register('confirm')}
        />
      </form>
    </Modal>
  );
}
