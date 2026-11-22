import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, CircleAlert, KeyRound, Pencil, UserPlus } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { usersApi } from '../../api/auth';
import { invoicesApi } from '../../api/billing';
import { parseApiError } from '../../api/errors';
import { genaiApi } from '../../api/genai';
import { mlApi } from '../../api/ml';
import { useToast } from '../../components/Toast';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/misc';
import { Spinner } from '../../components/ui/Spinner';
import { timeAgo } from '../../lib/format';
import { ROLE_TONE, roleLabel } from '../../lib/options';
import type { User } from '../../types';
import { useAuth } from '../auth/AuthContext';
import { SettingsSection } from './SettingsSection';
import { ResetPasswordModal, TeamMemberModal } from './TeamMemberModal';

export function TeamSection() {
  const { user: me } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<User | null>(null);
  const [adding, setAdding] = useState(false);
  const [resetting, setResetting] = useState<User | null>(null);

  const team = useQuery({
    queryKey: [usersApi.key, 'team'],
    queryFn: () => usersApi.list({ include_inactive: true }),
  });

  const toggleActive = useMutation({
    mutationFn: (u: User) => usersApi.update(u.id, { is_active: !u.is_active }),
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: [usersApi.key] });
      toast.success(
        saved.is_active ? `${saved.full_name} reactivated` : `${saved.full_name} deactivated`,
      );
    },
    onError: (err) => toast.error(parseApiError(err).message),
  });

  const members = team.data?.results ?? [];
  return (
    <SettingsSection
      id="team"
      title="Team"
      description="Add people, set their role, or deactivate someone who left. Their records stay."
      actions={
        <Button
          size="sm"
          onClick={() => {
            setEditing(null);
            setAdding(true);
          }}
        >
          <UserPlus className="size-4" aria-hidden />
          Add member
        </Button>
      }
    >
      {team.isLoading ? (
        <Spinner />
      ) : team.isError ? (
        <p className="text-sm text-rose-600">Couldn’t load the team.</p>
      ) : (
        <div className="-mx-5 overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-500 dark:border-slate-800">
                <th className="px-5 py-2 font-medium">Name</th>
                <th className="px-3 py-2 font-medium">Role</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium">Last sign-in</th>
                <th className="px-5 py-2 text-right font-medium">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {members.map((u) => {
                const isSelf = u.id === me?.id;
                return (
                  <tr
                    key={u.id}
                    className="border-b border-slate-100 last:border-0 dark:border-slate-800"
                  >
                    <td className="px-5 py-3">
                      <div className="font-medium">
                        {u.full_name}
                        {isSelf && <span className="ml-1 text-xs text-slate-500">(you)</span>}
                      </div>
                      <div className="text-xs text-slate-500">
                        {u.username} · {u.email}
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <Badge tone={ROLE_TONE[u.role]}>{roleLabel(u.role)}</Badge>
                    </td>
                    <td className="px-3 py-3">
                      {u.is_active ? (
                        <Badge tone="emerald">Active</Badge>
                      ) : (
                        <Badge tone="slate">Deactivated</Badge>
                      )}
                    </td>
                    <td className="px-3 py-3 text-slate-600 dark:text-slate-400">
                      {u.last_login ? timeAgo(u.last_login) : 'Never'}
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex justify-end gap-1">
                        <Button
                          size="sm"
                          variant="ghost"
                          aria-label={`Edit ${u.full_name}`}
                          onClick={() => setEditing(u)}
                        >
                          <Pencil className="size-3.5" aria-hidden />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          aria-label={`Reset password for ${u.full_name}`}
                          onClick={() => setResetting(u)}
                        >
                          <KeyRound className="size-3.5" aria-hidden />
                        </Button>
                        {!isSelf && (
                          <Button
                            size="sm"
                            variant="secondary"
                            loading={toggleActive.isPending && toggleActive.variables?.id === u.id}
                            onClick={() => toggleActive.mutate(u)}
                          >
                            {u.is_active ? 'Deactivate' : 'Reactivate'}
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <TeamMemberModal
        open={adding || editing !== null}
        member={editing}
        isSelf={editing?.id === me?.id}
        onClose={() => {
          setAdding(false);
          setEditing(null);
        }}
      />
      <ResetPasswordModal member={resetting} onClose={() => setResetting(null)} />
    </SettingsSection>
  );
}

function StatusRow({
  label,
  ok,
  detail,
  hint,
}: {
  label: string;
  ok: boolean | undefined;
  detail: string;
  hint?: string;
}) {
  return (
    <li className="flex items-start gap-3 py-3">
      {ok === undefined ? (
        <Spinner />
      ) : ok ? (
        <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-emerald-600" aria-label="Ready" />
      ) : (
        <CircleAlert className="mt-0.5 size-5 shrink-0 text-amber-500" aria-label="Not set up" />
      )}
      <div className="min-w-0">
        <p className="font-medium">{label}</p>
        <p className="text-sm text-slate-600 dark:text-slate-400">{detail}</p>
        {hint && <p className="mt-0.5 text-xs text-slate-500">{hint}</p>}
      </div>
    </li>
  );
}

export function SystemSection() {
  const ai = useQuery({ queryKey: [genaiApi.key, 'status'], queryFn: genaiApi.status });
  const payments = useQuery({ queryKey: ['billing', 'config'], queryFn: invoicesApi.config });
  const ml = useQuery({ queryKey: [mlApi.key, 'metrics'], queryFn: mlApi.metrics });
  const available = Object.entries(ml.data?.available ?? {});
  const loaded = available.filter(([, ok]) => ok).length;

  return (
    <SettingsSection
      id="system"
      title="System status"
      description="Integrations are configured on the server (environment variables), never in the browser."
    >
      <ul className="divide-y divide-slate-100 text-sm dark:divide-slate-800">
        <StatusRow
          label="AI (writer, summaries, Ask LeadPilot, agent)"
          ok={ai.isError ? false : ai.data?.configured}
          detail={
            ai.data?.configured
              ? `Connected: ${ai.data.provider} · ${ai.data.model}`
              : 'Offline mode: AI features return placeholder text.'
          }
          hint={ai.data?.configured ? undefined : 'Set GROQ_API_KEY on the server to enable it.'}
        />
        <StatusRow
          label="Payments (Razorpay)"
          ok={payments.isError ? false : payments.data?.configured}
          detail={
            payments.data?.configured
              ? `Connected in ${payments.data.test_mode ? 'test' : 'live'} mode (${payments.data.key_id})`
              : 'Not connected: invoices work, but Pay Now and payment links are off.'
          }
          hint={
            payments.data?.configured
              ? undefined
              : 'Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET (test keys) on the server.'
          }
        />
        <StatusRow
          label="Machine-learning models"
          ok={ml.isError ? false : ml.data ? loaded === available.length : undefined}
          detail={
            ml.data
              ? `${loaded} of ${available.length} models loaded (lead scoring, churn, segments, sentiment, forecast).`
              : 'Checking…'
          }
          hint={
            ml.data && loaded < available.length
              ? 'Missing models: retrain them on ML Insights.'
              : undefined
          }
        />
      </ul>
      <p className="mt-3 text-sm">
        <Link
          to="/ml-insights"
          className="font-medium text-indigo-600 hover:underline dark:text-indigo-400"
        >
          See model accuracy and retrain on ML Insights →
        </Link>
      </p>
    </SettingsSection>
  );
}
