import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { RefreshCw, Sparkles } from 'lucide-react';
import { useState } from 'react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { parseApiError } from '../../api/errors';
import { mlApi } from '../../api/ml';
import { useToast } from '../../components/Toast';
import { Button } from '../../components/ui/Button';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { Badge, PageHeader } from '../../components/ui/misc';
import { Spinner } from '../../components/ui/Spinner';
import { formatDateTime } from '../../lib/format';
import type { ModelMetrics, SegmentSummary } from '../../types';
import { useAuth } from '../auth/AuthContext';
import { ChartCard, TooltipBox } from '../dashboard/ChartCard';
import { useChartTheme } from '../dashboard/chartTheme';
import { ConfusionMatrix } from './ConfusionMatrix';
import { ForecastChart } from './ForecastChart';

const MODEL_INFO: Record<string, { title: string; purpose: string }> = {
  lead_score: { title: 'Lead scoring', purpose: 'Will this lead convert?' },
  churn: { title: 'Churn', purpose: 'Will this customer leave?' },
  segment: { title: 'Segmentation', purpose: 'RFM customer groups' },
  sentiment: { title: 'Ticket sentiment', purpose: 'Is this ticket angry?' },
  forecast: { title: 'Sales forecast', purpose: 'Revenue next 3 months' },
};
const CLASSIFIERS = ['lead_score', 'churn', 'sentiment'] as const;

const pct = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : `${(v * 100).toFixed(1)}%`;
const num = (v: number | null | undefined, digits = 3) =>
  v === null || v === undefined ? '—' : v.toFixed(digits);
const pretty = (name: string) => name.replace(/_/g, ' ');

function headline(m: ModelMetrics): string {
  if (m.task === 'classification') return `ROC-AUC ${num(m.test?.roc_auc)} · F1 ${num(m.test?.f1)}`;
  if (m.task === 'clustering') return `Silhouette ${num(m.silhouette)}`;
  return `MAE ${num(m.test?.mae, 0)} · RMSE ${num(m.test?.rmse, 0)}`;
}

export function MlInsightsPage() {
  const { hasRole } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<(typeof CLASSIFIERS)[number]>('lead_score');
  const [confirmRetrain, setConfirmRetrain] = useState(false);

  const metrics = useQuery({ queryKey: [mlApi.key, 'metrics'], queryFn: mlApi.metrics });
  const forecast = useQuery({ queryKey: [mlApi.key, 'forecast'], queryFn: mlApi.forecast });
  const segments = useQuery({ queryKey: [mlApi.key, 'segments'], queryFn: mlApi.segments });

  const refreshAll = () => queryClient.invalidateQueries();
  const retrain = useMutation({
    mutationFn: mlApi.retrain,
    onSuccess: (r) => {
      toast.success(r.status === 'done' ? 'Models retrained and applied' : 'Retraining started');
      setConfirmRetrain(false);
      refreshAll();
    },
    onError: (err) => toast.error(parseApiError(err).message),
  });
  const rescore = useMutation({
    mutationFn: mlApi.rescoreAll,
    onSuccess: () => {
      toast.success('Rescoring leads, segments and churn');
      refreshAll();
    },
    onError: (err) => toast.error(parseApiError(err).message),
  });

  const models = metrics.data?.models ?? {};
  const current = models[selected];

  return (
    <section>
      <PageHeader
        title="ML Insights"
        description="How the models behind scores, segments, churn, ticket priority and the forecast perform."
        actions={
          hasRole('admin') && (
            <>
              <Button
                variant="secondary"
                loading={rescore.isPending}
                onClick={() => rescore.mutate()}
              >
                <RefreshCw className="size-4" /> Rescore all
              </Button>
              <Button onClick={() => setConfirmRetrain(true)}>
                <Sparkles className="size-4" /> Retrain models
              </Button>
            </>
          )
        }
      />

      {metrics.isLoading ? (
        <div className="flex justify-center py-16">
          <Spinner label="Loading model metrics" />
        </div>
      ) : metrics.isError ? (
        <p className="py-16 text-center text-sm text-rose-600">
          {parseApiError(metrics.error).message}
        </p>
      ) : (
        <>
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Model metrics</caption>
              <thead className="border-b border-slate-200 bg-slate-50 text-xs text-slate-500 uppercase dark:border-slate-800 dark:bg-slate-900/60">
                <tr>
                  <th className="px-4 py-3">Model</th>
                  <th className="px-4 py-3">Trained on</th>
                  <th className="px-4 py-3">Chosen</th>
                  <th className="px-4 py-3">Test result</th>
                  <th className="hidden px-4 py-3 md:table-cell">Trained</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {Object.entries(MODEL_INFO).map(([key, info]) => {
                  const m = models[key];
                  return (
                    <tr key={key}>
                      <td className="px-4 py-3">
                        <p className="font-medium">{info.title}</p>
                        <p className="text-xs text-slate-500">{info.purpose}</p>
                      </td>
                      <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                        {m ? `${m.dataset} (${m.rows.toLocaleString('en-IN')} rows)` : '—'}
                      </td>
                      <td className="px-4 py-3">
                        {m ? (
                          <Badge tone="indigo">{pretty(m.chosen_model)}</Badge>
                        ) : (
                          <Badge tone="amber">Not trained</Badge>
                        )}
                      </td>
                      <td className="px-4 py-3 tabular-nums">{m ? headline(m) : '—'}</td>
                      <td className="hidden px-4 py-3 text-xs text-slate-500 md:table-cell">
                        {m ? formatDateTime(m.trained_at) : '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="mt-6">
            <div
              role="tablist"
              aria-label="Classifier"
              className="inline-flex rounded-lg border border-slate-200 bg-white p-1 dark:border-slate-800 dark:bg-slate-900"
            >
              {CLASSIFIERS.map((key) => (
                <button
                  key={key}
                  type="button"
                  role="tab"
                  aria-selected={selected === key}
                  onClick={() => setSelected(key)}
                  className={`rounded-md px-3 py-1.5 text-sm font-medium ${selected === key ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'}`}
                >
                  {MODEL_INFO[key].title}
                </button>
              ))}
            </div>
            {current ? (
              <div className="mt-4 grid gap-4 lg:grid-cols-2">
                <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
                  <h2 className="font-semibold">Confusion matrix (held-out test set)</h2>
                  <div className="mt-3">
                    {current.test?.confusion_matrix && (
                      <ConfusionMatrix
                        matrix={current.test.confusion_matrix}
                        caption={`Threshold 0.5 · precision ${pct(current.test.precision)} · recall ${pct(current.test.recall)}`}
                      />
                    )}
                  </div>
                </div>
                <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
                  <h2 className="font-semibold">Models compared (5-fold cross-validation)</h2>
                  <p className="mt-1 text-xs text-slate-500">{current.selection}</p>
                  <table className="mt-3 w-full text-sm">
                    <thead className="text-xs text-slate-500">
                      <tr>
                        <th className="py-1.5 text-left font-medium">Model</th>
                        <th className="py-1.5 text-right font-medium">ROC-AUC</th>
                        <th className="py-1.5 text-right font-medium">F1</th>
                        <th className="hidden py-1.5 text-right font-medium sm:table-cell">
                          Precision
                        </th>
                        <th className="hidden py-1.5 text-right font-medium sm:table-cell">
                          Recall
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                      {(current.comparison ?? []).map((row) => {
                        const chosen = row.model === current.chosen_model;
                        return (
                          <tr key={String(row.model)} className={chosen ? 'font-medium' : ''}>
                            <td className="py-1.5">
                              {pretty(String(row.model))}
                              {chosen && (
                                <span className="ml-2 text-xs text-indigo-600 dark:text-indigo-400">
                                  chosen
                                </span>
                              )}
                            </td>
                            <td className="py-1.5 text-right tabular-nums">
                              {num(row.cv_roc_auc as number)}
                            </td>
                            <td className="py-1.5 text-right tabular-nums">
                              {num(row.cv_f1 as number)}
                            </td>
                            <td className="hidden py-1.5 text-right tabular-nums sm:table-cell">
                              {num(row.cv_precision as number | undefined)}
                            </td>
                            <td className="hidden py-1.5 text-right tabular-nums sm:table-cell">
                              {num(row.cv_recall as number | undefined)}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <p className="mt-4 text-sm text-slate-500">
                This model hasn&apos;t been trained yet.
              </p>
            )}
          </div>
        </>
      )}

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        {forecast.data && (
          <ForecastChart data={forecast.data} className="lg:col-span-2" historyMonths={24} />
        )}
        {segments.data && <SegmentsCard data={segments.data} profile={models.segment?.profile} />}
        {models.segment?.k_comparison && <KChoiceCard metrics={models.segment} />}
      </div>

      <ConfirmDialog
        open={confirmRetrain}
        title="Retrain all models?"
        message="This retrains every model from the training datasets and re-applies them to all leads and customers. It can take a few minutes."
        confirmLabel="Retrain"
        loading={retrain.isPending}
        onConfirm={() => retrain.mutate()}
        onCancel={() => setConfirmRetrain(false)}
      />
    </section>
  );
}

function SegmentsCard({
  data,
  profile,
}: {
  data: SegmentSummary;
  profile?: ModelMetrics['profile'];
}) {
  const theme = useChartTheme();
  const rows = data.segments.map((s) => ({ ...s }));
  return (
    <ChartCard
      title="Customer segments"
      subtitle="Customers in each RFM segment (K-Means, k=4)"
      table={{
        headers: ['Segment', 'Customers', 'Avg churn risk', 'Training: median spend'],
        rows: rows.map((r) => [
          r.segment,
          r.customers,
          r.avg_churn_risk === null ? '—' : pct(r.avg_churn_risk),
          (() => {
            const p = profile?.find((x) => x.segment === r.segment);
            return p ? `£${Math.round(p.monetary).toLocaleString('en-GB')}` : '—';
          })(),
        ]),
      }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke={theme.grid} strokeWidth={1} />
          <XAxis
            dataKey="segment"
            tick={{ fontSize: 12, fill: theme.axis }}
            tickLine={false}
            axisLine={{ stroke: theme.grid }}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fontSize: 12, fill: theme.axis }}
            tickLine={false}
            axisLine={false}
            width={40}
          />
          <Tooltip
            cursor={{ fill: theme.grid, opacity: 0.5 }}
            content={({ active, payload, label }) =>
              active && payload?.length ? (
                <TooltipBox
                  title={String(label)}
                  lines={[
                    `${payload[0].value} customers`,
                    payload[0].payload.avg_churn_risk === null
                      ? 'No churn data'
                      : `Avg churn risk ${pct(payload[0].payload.avg_churn_risk)}`,
                  ]}
                />
              ) : null
            }
          />
          <Bar
            dataKey="customers"
            fill={theme.series}
            radius={[4, 4, 0, 0]}
            maxBarSize={48}
            isAnimationActive={false}
          />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

function KChoiceCard({ metrics }: { metrics: ModelMetrics }) {
  const theme = useChartTheme();
  const rows = metrics.k_comparison ?? [];
  return (
    <ChartCard
      title="Choosing k"
      subtitle={`Silhouette score per number of clusters (chosen: k=${metrics.chosen_model.replace('kmeans_k', '')})`}
      table={{
        headers: ['k', 'Silhouette', 'Inertia'],
        rows: rows.map((r) => [
          r.k,
          r.silhouette.toFixed(3),
          Math.round(r.inertia).toLocaleString('en-IN'),
        ]),
      }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke={theme.grid} strokeWidth={1} />
          <XAxis
            dataKey="k"
            tick={{ fontSize: 12, fill: theme.axis }}
            tickLine={false}
            axisLine={{ stroke: theme.grid }}
          />
          <YAxis
            domain={[0, 'auto']}
            tick={{ fontSize: 12, fill: theme.axis }}
            tickLine={false}
            axisLine={false}
            width={40}
          />
          <Tooltip
            cursor={{ fill: theme.grid, opacity: 0.5 }}
            content={({ active, payload, label }) =>
              active && payload?.length ? (
                <TooltipBox
                  title={`k = ${label}`}
                  lines={[`Silhouette ${Number(payload[0].value).toFixed(3)}`]}
                />
              ) : null
            }
          />
          <Bar
            dataKey="silhouette"
            fill={theme.series}
            radius={[4, 4, 0, 0]}
            maxBarSize={36}
            isAnimationActive={false}
          />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
