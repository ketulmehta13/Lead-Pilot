import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { genaiApi } from '../../api/genai';
import { ToastProvider } from '../../components/Toast';
import type { Activity, Contact } from '../../types';
import { ActivitySummary } from './ActivitySummary';
import { DraftEmailModal } from './DraftEmailModal';

vi.mock('../../api/genai', () => ({
  genaiApi: {
    key: 'genai',
    status: vi.fn(),
    draftEmail: vi.fn(),
    summarize: vi.fn(),
    actionItemsToTasks: vi.fn(),
  },
}));

const api = vi.mocked(genaiApi);

function wrap(ui: ReactNode) {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <ToastProvider>{ui}</ToastProvider>
    </QueryClientProvider>,
  );
}

const contact = {
  id: 7,
  full_name: 'Asha Rao',
  first_name: 'Asha',
  email: 'asha@acme.io',
} as Contact;
const longNotes =
  'Demo went well. Asha wants pricing for 25 seats by Friday and asked us to set up a call with their CFO. ' +
  'Main concern is onboarding time; she wants a 2-week rollout plan as part of the proposal, plus references from two similar customers.';

beforeEach(() => {
  vi.clearAllMocks();
  api.status.mockResolvedValue({ configured: true, provider: 'groq', model: 'llama' });
});

describe('DraftEmailModal', () => {
  it('drafts an editable email with the chosen goal and tone', async () => {
    api.draftEmail.mockResolvedValue({
      subject: 'Pricing for 25 seats',
      body: 'Hi Asha,\nAs promised…',
    });
    const user = userEvent.setup();
    wrap(<DraftEmailModal contact={contact} onClose={() => {}} />);
    await user.click(screen.getByRole('button', { name: 'Send the proposal' }));
    await user.selectOptions(screen.getByRole('combobox'), 'concise');
    await user.click(screen.getByRole('button', { name: /draft with ai/i }));
    expect(await screen.findByDisplayValue('Pricing for 25 seats')).toBeInTheDocument();
    expect(api.draftEmail).toHaveBeenCalledWith({
      contact_id: 7,
      goal: 'Send the proposal',
      tone: 'concise',
    });
    const subject = screen.getByDisplayValue('Pricing for 25 seats');
    await user.clear(subject);
    await user.type(subject, 'Edited subject');
    expect(screen.getByRole('link', { name: /open in email app/i })).toHaveAttribute(
      'href',
      expect.stringContaining('Edited%20subject'),
    );
  });

  it('shows the offline notice when no LLM key is configured', async () => {
    api.status.mockResolvedValue({ configured: false, provider: 'mock', model: 'mock-1' });
    wrap(<DraftEmailModal contact={contact} onClose={() => {}} />);
    expect(await screen.findByText(/offline mode/i)).toBeInTheDocument();
  });
});

describe('ActivitySummary', () => {
  const activity = { id: 3, body: longNotes, summary: null, action_items: null } as Activity;

  it('hides the button for short notes', () => {
    wrap(<ActivitySummary activity={{ ...activity, body: 'Quick call.' }} />);
    expect(screen.queryByRole('button', { name: /summarize/i })).not.toBeInTheDocument();
  });

  it('summarizes and turns chosen action items into tasks', async () => {
    api.summarize.mockResolvedValue({
      activity_id: 3,
      summary: 'Asha wants pricing for 25 seats.',
      sentiment: 'positive',
      action_items: [
        { title: 'Send pricing', due_in_days: 2 },
        { title: 'Book CFO call', due_in_days: null },
      ],
    });
    api.actionItemsToTasks.mockResolvedValue([]);
    const user = userEvent.setup();
    wrap(<ActivitySummary activity={activity} />);
    await user.click(screen.getByRole('button', { name: /summarize/i }));
    expect(await screen.findByText('Asha wants pricing for 25 seats.')).toBeInTheDocument();
    expect(screen.getByText('positive')).toBeInTheDocument();
    await user.click(screen.getByRole('checkbox', { name: /book cfo call/i })); // untick
    await user.click(screen.getByRole('button', { name: /create 1 task/i }));
    expect(api.actionItemsToTasks).toHaveBeenCalledWith(3, [0]);
  });
});
