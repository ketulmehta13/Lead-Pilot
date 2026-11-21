import { useMutation, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, FileUp, TriangleAlert } from 'lucide-react';
import { useState } from 'react';
import { companiesApi, contactsApi } from '../../api/crm';
import { parseApiError } from '../../api/errors';
import { Button } from '../../components/ui/Button';
import { Modal } from '../../components/ui/Modal';
import type { ImportResult } from '../../types';

const SAMPLE =
  'first_name,last_name,email,phone,company,tags\n' +
  'Asha,Rao,asha@acme.io,+91 98765 43210,Acme Pvt Ltd,vip;newsletter\n';

export function ImportContactsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);

  const mutation = useMutation({
    mutationFn: (f: File) => contactsApi.importCsv(f),
    onSuccess: (data) => {
      setResult(data);
      if (data.created) {
        queryClient.invalidateQueries({ queryKey: [contactsApi.key] });
        queryClient.invalidateQueries({ queryKey: [companiesApi.key] });
      }
    },
  });

  const sampleHref = `data:text/csv;charset=utf-8,${encodeURIComponent(SAMPLE)}`;

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      title="Import contacts from CSV"
      footer={
        result ? (
          <Button onClick={onClose}>Done</Button>
        ) : (
          <>
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button
              disabled={!file}
              loading={mutation.isPending}
              onClick={() => file && mutation.mutate(file)}
            >
              Import
            </Button>
          </>
        )
      }
    >
      {!result ? (
        <div className="space-y-4 text-sm">
          <p className="text-slate-600 dark:text-slate-300">
            Columns: <code>first_name</code> and <code>email</code> are required;{' '}
            <code>last_name</code>, <code>phone</code>, <code>company</code>, <code>tags</code>{' '}
            (separated by <code>;</code>) are optional. Max 2 MB.{' '}
            <a
              href={sampleHref}
              download="contacts-sample.csv"
              className="text-indigo-600 hover:underline dark:text-indigo-400"
            >
              Download a sample
            </a>
          </p>
          <label className="flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed border-slate-300 px-4 py-8 text-center hover:border-indigo-400 dark:border-slate-700">
            <FileUp className="size-8 text-slate-400" aria-hidden />
            <span className="font-medium">{file ? file.name : 'Choose a .csv file'}</span>
            <input
              type="file"
              accept=".csv,text/csv"
              className="sr-only"
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null);
                mutation.reset();
              }}
            />
          </label>
          {mutation.isError && (
            <p role="alert" className="text-rose-600">
              {parseApiError(mutation.error).message}
            </p>
          )}
        </div>
      ) : (
        <ImportSummary result={result} />
      )}
    </Modal>
  );
}

function ImportSummary({ result }: { result: ImportResult }) {
  return (
    <div className="space-y-4 text-sm">
      <div className="flex items-center gap-2">
        <CheckCircle2 className="size-5 text-emerald-500" aria-hidden />
        <p>
          Imported <strong>{result.created}</strong> of {result.total_rows} rows.
        </p>
      </div>
      {result.errors.length > 0 && (
        <div>
          <div className="mb-2 flex items-center gap-2 text-amber-700 dark:text-amber-400">
            <TriangleAlert className="size-4" aria-hidden />
            <p className="font-medium">{result.errors.length} rows were skipped</p>
          </div>
          <div className="max-h-64 overflow-y-auto rounded-lg border border-slate-200 dark:border-slate-700">
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 bg-slate-50 dark:bg-slate-800">
                <tr>
                  <th className="px-3 py-2">Line</th>
                  <th className="px-3 py-2">Problem</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {result.errors.map((e) => (
                  <tr key={e.row}>
                    <td className="px-3 py-2 font-mono">{e.row}</td>
                    <td className="px-3 py-2">
                      {Object.entries(e.errors)
                        .map(([field, msgs]) => `${field}: ${msgs.join(' ')}`)
                        .join(' · ')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
