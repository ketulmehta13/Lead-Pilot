import type { ConfusionMatrix as Matrix } from '../../types';

/** 2x2 confusion matrix as a heatmap: one blue hue, light -> dark by count, every cell
 * labelled with its count and share so colour is never the only cue. */
export function ConfusionMatrix({ matrix, caption }: { matrix: Matrix; caption: string }) {
  const [negLabel, posLabel] = matrix.labels;
  const cells = matrix.matrix.flat();
  const max = Math.max(...cells, 1);
  const total = cells.reduce((a, b) => a + b, 0) || 1;
  const names = [
    ['True negative', 'False positive'],
    ['False negative', 'True positive'],
  ];

  return (
    <figure>
      <table className="w-full table-fixed border-separate border-spacing-0.5 text-center text-sm">
        <caption className="mb-2 text-left text-xs text-slate-500">{caption}</caption>
        <thead>
          <tr>
            <th className="w-28" />
            <th scope="col" className="pb-1 text-xs font-medium text-slate-500">
              Predicted {negLabel}
            </th>
            <th scope="col" className="pb-1 text-xs font-medium text-slate-500">
              Predicted {posLabel}
            </th>
          </tr>
        </thead>
        <tbody>
          {matrix.matrix.map((row, i) => (
            <tr key={i}>
              <th scope="row" className="pr-2 text-right text-xs font-medium text-slate-500">
                Actual {i === 0 ? negLabel : posLabel}
              </th>
              {row.map((count, j) => {
                const strength = count / max;
                const dark = strength > 0.55;
                return (
                  <td
                    key={j}
                    className="rounded-md py-4"
                    style={{
                      backgroundColor: `color-mix(in oklab, #2a78d6 ${Math.round(12 + strength * 78)}%, transparent)`,
                    }}
                    title={names[i][j]}
                  >
                    <span
                      className={`block text-base font-semibold tabular-nums ${dark ? 'text-white' : 'text-slate-900 dark:text-slate-100'}`}
                    >
                      {count}
                    </span>
                    <span
                      className={`block text-xs ${dark ? 'text-white/85' : 'text-slate-600 dark:text-slate-300'}`}
                    >
                      {names[i][j]} · {Math.round((100 * count) / total)}%
                    </span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
