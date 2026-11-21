import type { ForecastResponse } from '../../types';
import { formatMonth } from '../dashboard/chartTheme';

export interface Row {
  month: string;
  label: string;
  revenue?: number;
  forecast?: number;
  band?: [number, number];
}

/** Turn the API response into chart rows. The forecast line starts at the last actual month
 * so the two lines join instead of leaving a gap. */
export function forecastRows(data: ForecastResponse, historyMonths = 12): Row[] {
  const history = (data.history ?? []).slice(-historyMonths);
  const rows: Row[] = history.map((h) => ({
    month: h.month,
    label: formatMonth(h.month),
    revenue: h.revenue,
  }));
  const last = rows[rows.length - 1];
  if (last && data.forecast?.length) {
    last.forecast = last.revenue;
    last.band = [last.revenue ?? 0, last.revenue ?? 0];
  }
  for (const f of data.forecast ?? []) {
    rows.push({
      month: f.month,
      label: formatMonth(f.month),
      forecast: f.forecast,
      band: [f.lower, f.upper],
    });
  }
  return rows;
}
