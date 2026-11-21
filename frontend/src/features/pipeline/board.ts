import type { BoardColumn, DealStage } from '../../types';

export const STAGES: DealStage[] = ['new', 'qualified', 'proposal', 'negotiation', 'won', 'lost'];

/** Recompute each column's count and total from its cards. */
export function withTotals(columns: BoardColumn[]): BoardColumn[] {
  return columns.map((col) => ({
    ...col,
    count: col.deals.length,
    total_value: col.deals.reduce((sum, d) => sum + Number(d.value), 0).toFixed(2),
  }));
}

/** Where a deal currently sits: [stage, index] or null if it isn't on the board. */
export function locate(columns: BoardColumn[], dealId: number): [DealStage, number] | null {
  for (const col of columns) {
    const index = col.deals.findIndex((d) => d.id === dealId);
    if (index !== -1) return [col.stage, index];
  }
  return null;
}

/**
 * Pure board update used for the optimistic UI: move `dealId` to `toStage` at `toIndex`
 * (index among the cards shown in that column). Returns a new board with fresh totals.
 */
export function applyMove(
  columns: BoardColumn[],
  dealId: number,
  toStage: DealStage,
  toIndex: number,
): BoardColumn[] {
  const from = locate(columns, dealId);
  if (!from) return columns;
  const deal = columns.find((c) => c.stage === from[0])!.deals[from[1]];
  const stripped = columns.map((col) => ({
    ...col,
    deals: col.deals.filter((d) => d.id !== dealId),
  }));
  const moved = { ...deal, stage: toStage };
  const next = stripped.map((col) => {
    if (col.stage !== toStage) return col;
    const index = Math.max(0, Math.min(toIndex, col.deals.length));
    const deals = [...col.deals];
    deals.splice(index, 0, moved);
    return { ...col, deals };
  });
  return withTotals(next);
}
