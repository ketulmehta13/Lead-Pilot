import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, CheckSquare, IndianRupee, Kanban, LifeBuoy, Trophy } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { analyticsApi } from '../../api/analytics';
import { parseApiError } from '../../api/errors';
import { PageHeader } from '../../components/ui/misc';
import { Spinner } from '../../components/ui/Spinner';
import { formatINR, timeAgo } from '../../lib/format';
import type { DashboardSummary } from '../../types';
import { useAuth } from '../auth/AuthContext';
import { ChartCard, TooltipBox } from './ChartCard';
import { formatCompactINR, formatMonth, useChartTheme } from './chartTheme';

export function DashboardPage() {
  const { user, hasRole } = useAuth();
  const canSeeSales = hasRole('admin', 'sales');
  const query = useQuery({
    queryKey: [analyticsApi.key, 'summary'],
    queryFn: analyticsApi.summary,
    enabled: canSeeSales,
    refetchInterval: 60_000,
  });

  const title = 'Dashboard';
  const greeting = `Welcome back, ${user?.first_name || user?.username}.`;

  if (!canSeeSales) {
    return (
      <section>
        <PageHeader title={title} description={greeting} />
        <div className="rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
          <LifeBuoy className="size-8 text-indigo-500" aria-hidden />
          <p className="mt-3 font-medium">Support metrics arrive with Smart Tickets (Phase 3).</p>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
            Meanwhile you can look up any customer in{' '}
            <Link to="/contacts" className="text-indigo-600 hover:underline dark:text-indigo-400">
              Contacts
            </Link>
            .
          </p>
        </div>
      </section>
    );
  }

  return (
    <section>
      <PageHeader
        title={title}
        description={
          hasRole('admin') ? `${greeting} Company-wide numbers.` : `${greeting} Your numbers.`
        }
      />
      {query.isLoading ? (
        <div className="flex justify-center py-20">
          <Spinner label="Loading dashboard" />
        </div>
      ) : query.isError || !query.data ? (
        <p className="py-20 text-center text-sm text-rose-600">
          {parseApiError(query.error).message}
        </p>
      ) : (
        <DashboardBody data={query.data} />
      )}
    </section>
  );
}

function DashboardBody({ data }: { data: DashboardSummary }) {
  const t = data.totals;
  return (
    <>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          icon={<Kanban className="size-4" />}
          label="Open pipeline"
          value={formatINR(t.pipeline_value)}
          sub={`${t.open_deals} open deals · ${formatINR(t.weighted_pipeline_value)} weighted`}
          to="/pipeline"
        />
        <StatTile
          icon={<IndianRupee className="size-4" />}
          label="Revenue this month"
          value={formatINR(data.revenue_this_month)}
          sub="Value of deals won this month"
        />
        <StatTile
          icon={<Trophy className="size-4" />}
          label="Win rate"
          value={data.win_rate === null ? '—' : `${data.win_rate}%`}
          sub="Won ÷ (won + lost), all time"
        />
        <StatTile
          icon={<CheckSquare className="size-4" />}
          label="Tasks due today"
          value={String(data.tasks_due_today)}
          sub={
            data.tasks_overdue > 0 ? (
              <span className="inline-flex items-center gap-1 font-medium text-rose-600 dark:text-rose-400">
                <AlertTriangle className="size-3.5" aria-hidden /> {data.tasks_overdue} overdue
              </span>
            ) : (
              'Nothing overdue'
            )
          }
          to="/tasks"
        />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <RevenueTrend data={data} />
        <PipelineByStage data={data} />
        <LeadsBySource data={data} />
        <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm dark:border-slate-800 dark:bg-slate-900">
          <h2 className="font-semibold">At a glance</h2>
          <dl className="mt-3 grid grid-cols-2 gap-y-3">
            <dt className="text-slate-500">Leads</dt>
            <dd className="text-right font-medium tabular-nums">{t.leads}</dd>
            <dt className="text-slate-500">Open leads</dt>
            <dd className="text-right font-medium tabular-nums">{t.open_leads}</dd>
            <dt className="text-slate-500">Open deals</dt>
            <dd className="text-right font-medium tabular-nums">{t.open_deals}</dd>
            <dt className="text-slate-500">Updated</dt>
            <dd className="text-right text-slate-500">{timeAgo(data.generated_at)}</dd>
          </dl>
        </div>
      </div>
    </>
  );
}

function StatTile({
  icon,
  label,
  value,
  sub,
  to,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  sub: ReactNode;
  to?: string;
}) {
  const body = (
    <>
      <p className="flex items-center gap-2 text-sm text-slate-500">
        <span className="text-indigo-500">{icon}</span>
        {label}
      </p>
      <p className="mt-2 text-2xl font-semibold tracking-tight tabular-nums">{value}</p>
      <p className="mt-1 text-xs text-slate-500">{sub}</p>
    </>
  );
  const cls =
    'block rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900';
  return to ? (
    <Link to={to} className={`${cls} hover:border-indigo-300 dark:hover:border-indigo-500/50`}>
      {body}
    </Link>
  ) : (
    <div className={cls}>{body}</div>
  );
}

const AXIS_TICK = { fontSize: 12 };

function RevenueTrend({ data }: { data: DashboardSummary }) {
  const theme = useChartTheme();
  const rows = data.revenue_trend.map((m) => ({
    month: formatMonth(m.month),
    revenue: Number(m.revenue),
    deals: m.deals,
  }));
  return (
    <ChartCard
      title="Revenue trend"
      subtitle="Value of deals won per month, last 12 months"
      className="lg:col-span-2"
      table={{
        headers: ['Month', 'Revenue', 'Deals won'],
        rows: rows.map((r) => [r.month, formatINR(r.revenue), r.deals]),
      }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke={theme.grid} strokeWidth={1} />
          <XAxis
            dataKey="month"
            tick={{ ...AXIS_TICK, fill: theme.axis }}
            tickLine={false}
            axisLine={{ stroke: theme.grid }}
            interval="preserveStartEnd"
          />
          <YAxis
            tickFormatter={formatCompactINR}
            tick={{ ...AXIS_TICK, fill: theme.axis }}
            tickLine={false}
            axisLine={false}
            width={64}
          />
          <Tooltip
            cursor={{ stroke: theme.axis, strokeWidth: 1 }}
            content={({ active, payload, label }) =>
              active && payload?.length ? (
                <TooltipBox
                  title={String(label)}
                  lines={[
                    formatINR(payload[0].value as number),
                    `${payload[0].payload.deals} deals won`,
                  ]}
                />
              ) : null
            }
          />
          <Area
            type="monotone"
            dataKey="revenue"
            stroke={theme.series}
            strokeWidth={2}
            fill={theme.seriesFill}
            dot={false}
            activeDot={{ r: 5, fill: theme.series, stroke: theme.surface, strokeWidth: 2 }}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

function PipelineByStage({ data }: { data: DashboardSummary }) {
  const theme = useChartTheme();
  const rows = data.deals_by_stage.map((s) => ({
    label: s.label,
    value: Number(s.value),
    count: s.count,
  }));
  return (
    <ChartCard
      title="Pipeline by stage"
      subtitle="Total deal value in each stage"
      table={{
        headers: ['Stage', 'Value', 'Deals'],
        rows: rows.map((r) => [r.label, formatINR(r.value), r.count]),
      }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke={theme.grid} strokeWidth={1} />
          <XAxis
            dataKey="label"
            tick={{ ...AXIS_TICK, fill: theme.axis }}
            tickLine={false}
            axisLine={{ stroke: theme.grid }}
            interval={0}
          />
          <YAxis
            tickFormatter={formatCompactINR}
            tick={{ ...AXIS_TICK, fill: theme.axis }}
            tickLine={false}
            axisLine={false}
            width={64}
          />
          <Tooltip
            cursor={{ fill: theme.grid, opacity: 0.5 }}
            content={({ active, payload, label }) =>
              active && payload?.length ? (
                <TooltipBox
                  title={String(label)}
                  lines={[
                    formatINR(payload[0].value as number),
                    `${payload[0].payload.count} deals`,
                  ]}
                />
              ) : null
            }
          />
          <Bar
            dataKey="value"
            fill={theme.series}
            radius={[4, 4, 0, 0]}
            maxBarSize={40}
            isAnimationActive={false}
          />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

function LeadsBySource({ data }: { data: DashboardSummary }) {
  const theme = useChartTheme();
  const rows = [...data.leads_by_source]
    .sort((a, b) => b.count - a.count)
    .map((s) => ({ label: s.label, count: s.count }));
  return (
    <ChartCard
      title="Leads by source"
      subtitle="Number of leads from each channel"
      table={{ headers: ['Source', 'Leads'], rows: rows.map((r) => [r.label, r.count]) }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={rows}
          layout="vertical"
          margin={{ top: 0, right: 16, bottom: 0, left: 0 }}
          barCategoryGap={8}
        >
          <CartesianGrid horizontal={false} stroke={theme.grid} strokeWidth={1} />
          <XAxis
            type="number"
            allowDecimals={false}
            tick={{ ...AXIS_TICK, fill: theme.axis }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            type="category"
            dataKey="label"
            tick={{ ...AXIS_TICK, fill: theme.axis }}
            tickLine={false}
            axisLine={{ stroke: theme.grid }}
            width={96}
          />
          <Tooltip
            cursor={{ fill: theme.grid, opacity: 0.5 }}
            content={({ active, payload, label }) =>
              active && payload?.length ? (
                <TooltipBox title={String(label)} lines={[`${payload[0].value} leads`]} />
              ) : null
            }
          />
          <Bar
            dataKey="count"
            fill={theme.series}
            radius={[0, 4, 4, 0]}
            maxBarSize={28}
            isAnimationActive={false}
          />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
