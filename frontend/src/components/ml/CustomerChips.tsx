import { Badge, type Tone } from '../ui/misc';

const SEGMENT_TONE: Record<string, Tone> = {
  Champions: 'emerald',
  Loyal: 'indigo',
  'At Risk': 'amber',
  Lost: 'slate',
};

export function SegmentChip({ segment }: { segment: string | null }) {
  if (!segment) return null;
  return (
    <span title="RFM segment (K-Means)">
      <Badge tone={SEGMENT_TONE[segment] ?? 'slate'}>{segment}</Badge>
    </span>
  );
}

function churnLevel(risk: number): { label: string; tone: Tone } {
  if (risk >= 0.6) return { label: 'High', tone: 'rose' };
  if (risk >= 0.3) return { label: 'Medium', tone: 'amber' };
  return { label: 'Low', tone: 'emerald' };
}

/** Churn probability as a level + percentage (never colour alone). */
export function ChurnChip({ risk }: { risk: number | null }) {
  if (risk === null || risk === undefined) return null;
  const { label, tone } = churnLevel(risk);
  return (
    <span title="Probability this customer churns">
      <Badge tone={tone}>
        Churn {label} · {Math.round(risk * 100)}%
      </Badge>
    </span>
  );
}
