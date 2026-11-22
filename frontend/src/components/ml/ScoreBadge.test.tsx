import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { ScoreFactor } from '../../types';
import { ScoreBadge } from './ScoreBadge';

const factors: ScoreFactor[] = [
  {
    feature: 'engagement_min',
    label: 'Engagement time',
    value: '30 min',
    impact: 1.2,
    direction: 'up',
  },
  { feature: 'last_touch', label: 'Last interaction', value: 'call', impact: 0.6, direction: 'up' },
  { feature: 'source', label: 'Lead source', value: 'cold', impact: -0.4, direction: 'down' },
];

describe('ScoreBadge', () => {
  it('shows score and label, and explains it on demand', async () => {
    const user = userEvent.setup();
    render(<ScoreBadge score={82} label="hot" factors={factors} />);
    expect(screen.getByText('82')).toBeInTheDocument();
    expect(screen.getByText('Hot')).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /why\?/i }));
    const dialog = screen.getByRole('dialog', { name: /why this lead scores 82/i });
    expect(dialog).toHaveTextContent('Engagement time: 30 min');
    expect(dialog).toHaveTextContent('Lowers the score');

    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('opens outside clipped containers (tables) and closes when clicking elsewhere', async () => {
    const user = userEvent.setup();
    const { container } = render(
      <div style={{ overflow: 'hidden', height: 20 }}>
        <ScoreBadge score={60} label="warm" factors={factors} />
        <button type="button">elsewhere</button>
      </div>,
    );
    await user.click(screen.getByRole('button', { name: /why\?/i }));
    const panel = screen.getByRole('dialog', { name: 'Why this lead scores 60' });
    // Portalled to <body> with fixed positioning, so overflow:hidden can't cut it off.
    expect(container.contains(panel)).toBe(false);
    expect(panel.style.position).toBe('fixed');
    // Clicks inside the panel keep it open; clicks elsewhere close it.
    await user.click(panel);
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'elsewhere' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('says when a lead has not been scored', () => {
    render(<ScoreBadge score={null} label={null} factors={null} />);
    expect(screen.getByText('Not scored')).toBeInTheDocument();
  });
});
