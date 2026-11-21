import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { formatINR } from '../../lib/format';
import type { ForecastResponse } from '../../types';
import { ChartCard, TooltipBox } from '../dashboard/ChartCard';
import { formatCompactINR, formatMonth, useChartTheme } from '../dashboard/chartTheme';
import { forecastRows, type Row } from './forecastRows';

export function ForecastChart({
  data,
  title = 'Revenue forecast',
  className = '',
  historyMonths = 12,
}: {
  data: ForecastResponse;
  title?: string;
  className?: string;
  historyMonths?: number;
}) {
  const theme = useChartTheme();

  if (!data.ok) {
    return (
      <div
        className={`rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900 ${className}`}
      >
        <h2 className="font-semibold">{title}</h2>
        <p className="mt-2 text-sm text-slate-500">{data.reason}</p>
      </div>
    );
  }

  const rows = forecastRows(data, historyMonths);
  const chosen = data.methods?.find((m) => m.method === data.chosen);
  const tableRows = [
    ...(data.history ?? [])
      .slice(-historyMonths)
      .map((h) => [formatMonth(h.month), formatINR(h.revenue), 'Actual', '']),
    ...(data.forecast ?? []).map((f) => [
      formatMonth(f.month),
      formatINR(f.forecast),
      'Forecast',
      `${formatINR(f.lower)} – ${formatINR(f.upper)}`,
    ]),
  ];

  return (
    <ChartCard
      title={title}
      subtitle={`Won-deal revenue: last ${historyMonths} months and next 3 (shaded: ~95% range${chosen ? `; ${chosen.method.replace(/_/g, ' ')}, backtest MAE ${formatCompactINR(chosen.mae)}` : ''})`}
      className={className}
      table={{ headers: ['Month', 'Revenue', 'Type', '95% range'], rows: tableRows }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke={theme.grid} strokeWidth={1} />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 12, fill: theme.axis }}
            tickLine={false}
            axisLine={{ stroke: theme.grid }}
            interval="preserveStartEnd"
          />
          <YAxis
            tickFormatter={formatCompactINR}
            tick={{ fontSize: 12, fill: theme.axis }}
            tickLine={false}
            axisLine={false}
            width={64}
          />
          <Tooltip
            cursor={{ stroke: theme.axis, strokeWidth: 1 }}
            content={({ active, payload, label }) => {
              if (!active || !payload?.length) return null;
              const row = payload[0].payload as Row;
              const lines =
                row.revenue !== undefined
                  ? [`Actual ${formatINR(row.revenue)}`]
                  : [
                      `Forecast ${formatINR(row.forecast ?? 0)}`,
                      `Range ${formatINR(row.band?.[0] ?? 0)} – ${formatINR(row.band?.[1] ?? 0)}`,
                    ];
              return <TooltipBox title={String(label)} lines={lines} />;
            }}
          />
          <Area
            dataKey="band"
            stroke="none"
            fill={theme.seriesFill}
            isAnimationActive={false}
            activeDot={false}
          />
          <Line
            dataKey="revenue"
            stroke={theme.series}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 5, fill: theme.series, stroke: theme.surface, strokeWidth: 2 }}
            isAnimationActive={false}
          />
          <Line
            dataKey="forecast"
            stroke={theme.series}
            strokeWidth={2}
            strokeDasharray="6 4"
            dot={false}
            activeDot={{ r: 5, fill: theme.surface, stroke: theme.series, strokeWidth: 2 }}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
