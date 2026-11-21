import { describe, expect, it } from 'vitest';
import { forecastRows } from './forecastRows';

describe('forecastRows', () => {
  it('joins the forecast line onto the last actual month', () => {
    const rows = forecastRows({
      ok: true,
      history: [
        { month: '2026-10', revenue: 100 },
        { month: '2026-11', revenue: 120 },
      ],
      forecast: [{ month: '2026-12', forecast: 130, lower: 90, upper: 170 }],
    });
    expect(rows.map((r) => r.month)).toEqual(['2026-10', '2026-11', '2026-12']);
    expect(rows[1]).toMatchObject({ revenue: 120, forecast: 120, band: [120, 120] });
    expect(rows[2]).toMatchObject({ forecast: 130, band: [90, 170] });
    expect(rows[2].revenue).toBeUndefined();
  });

  it('keeps only the requested number of history months', () => {
    const history = Array.from({ length: 24 }, (_, i) => ({
      month: `2025-${String((i % 12) + 1).padStart(2, '0')}`,
      revenue: i,
    }));
    expect(forecastRows({ ok: true, history, forecast: [] }, 12)).toHaveLength(12);
  });
});
