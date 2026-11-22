import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { ScoreBadge } from './ScoreBadge';

const factors = [
  {
    feature: 'n_activities',
    label: 'Number of interactions',
    value: '0',
    impact: 0.66,
    direction: 'up' as const,
  },
];

describe('ScoreBadge', () => {
  it('opens the "Why?" panel outside clipped containers and closes on Escape', async () => {
    const user = userEvent.setup();
    const { container } = render(
      <div style={{ overflow: 'hidden', height: 20 }}>
        <ScoreBadge score={60} label="warm" factors={factors} />
      </div>,
    );
    await user.click(screen.getByRole('button', { name: /why\?/i }));
    const panel = screen.getByRole('dialog', { name: 'Why this lead scores 60' });
    // Portalled to <body>, so a table/card with overflow:hidden can't cut it off.
    expect(container.contains(panel)).toBe(false);
    expect(panel.style.position).toBe('fixed');
    expect(panel).toHaveTextContent('Number of interactions');
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
