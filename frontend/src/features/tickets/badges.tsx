import { AlertOctagon, Frown, Meh, Smile, Zap } from 'lucide-react';
import { Badge } from '../../components/ui/misc';
import type { Sentiment, TicketPriority } from '../../types';

export function PriorityBadge({
  priority,
  urgent,
}: {
  priority: TicketPriority;
  urgent?: boolean;
}) {
  const tone = priority === 'high' ? 'rose' : priority === 'medium' ? 'amber' : 'slate';
  return (
    <Badge tone={tone}>
      {priority === 'high' && <AlertOctagon className="mr-1 size-3" aria-hidden />}
      {priority.charAt(0).toUpperCase() + priority.slice(1)}
      {urgent && <Zap className="ml-1 size-3" aria-label="urgent keywords found" />}
    </Badge>
  );
}

/** Sentiment with an icon and label, never colour alone. */
export function SentimentBadge({
  sentiment,
  score,
}: {
  sentiment: Sentiment | null;
  score: number | null;
}) {
  if (!sentiment) return <span className="text-xs text-slate-400">—</span>;
  const Icon = sentiment === 'positive' ? Smile : sentiment === 'negative' ? Frown : Meh;
  const tone = sentiment === 'positive' ? 'emerald' : sentiment === 'negative' ? 'rose' : 'slate';
  return (
    <span title={score !== null ? `Sentiment score ${score.toFixed(2)} (-1 to +1)` : undefined}>
      <Badge tone={tone}>
        <Icon className="mr-1 size-3" aria-hidden />
        {sentiment.charAt(0).toUpperCase() + sentiment.slice(1)}
      </Badge>
    </span>
  );
}
