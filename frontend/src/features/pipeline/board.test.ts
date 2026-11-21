import { describe, expect, it } from 'vitest';
import type { BoardColumn, Deal, DealStage } from '../../types';
import { applyMove, locate } from './board';
import { STAGES } from './board';

function deal(id: number, stage: DealStage, value = '100'): Deal {
  return {
    id,
    stage,
    value,
    title: `D${id}`,
    contact: 1,
    contact_name: 'C',
    company_name: null,
    lead: null,
    expected_close_date: null,
    probability: 10,
    position: 0,
    closed_at: null,
    owner: 1,
    owner_name: null,
    created_at: '',
    updated_at: '',
  };
}

function board(layout: Partial<Record<DealStage, Deal[]>>): BoardColumn[] {
  return STAGES.map((stage) => ({
    stage,
    label: stage,
    count: layout[stage]?.length ?? 0,
    total_value: '0',
    deals: layout[stage] ?? [],
  }));
}

const ids = (cols: BoardColumn[], stage: DealStage) =>
  cols.find((c) => c.stage === stage)!.deals.map((d) => d.id);

describe('applyMove', () => {
  const start = board({
    new: [deal(1, 'new', '100'), deal(2, 'new', '200'), deal(3, 'new', '300')],
    won: [deal(4, 'won', '1000')],
  });

  it('reorders inside a column', () => {
    const next = applyMove(start, 3, 'new', 0);
    expect(ids(next, 'new')).toEqual([3, 1, 2]);
  });

  it('moves across columns, updates stage and both columns totals', () => {
    const next = applyMove(start, 2, 'won', 1);
    expect(ids(next, 'new')).toEqual([1, 3]);
    expect(ids(next, 'won')).toEqual([4, 2]);
    const won = next.find((c) => c.stage === 'won')!;
    expect(won.count).toBe(2);
    expect(won.total_value).toBe('1200.00');
    expect(won.deals[1].stage).toBe('won');
    expect(next.find((c) => c.stage === 'new')!.total_value).toBe('400.00');
  });

  it('clamps the index and handles empty columns', () => {
    expect(ids(applyMove(start, 1, 'lost', 99), 'lost')).toEqual([1]);
    expect(ids(applyMove(start, 1, 'new', -5), 'new')).toEqual([1, 2, 3]);
  });

  it('does not mutate the input board', () => {
    applyMove(start, 1, 'won', 0);
    expect(ids(start, 'new')).toEqual([1, 2, 3]);
  });

  it('ignores unknown deals', () => {
    expect(applyMove(start, 999, 'won', 0)).toBe(start);
    expect(locate(start, 999)).toBeNull();
  });
});
