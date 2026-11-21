import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  closestCorners,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragOverEvent,
  type DragStartEvent,
  type UniqueIdentifier,
} from '@dnd-kit/core';
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CalendarClock, GripVertical, Plus } from 'lucide-react';
import { useRef, useState } from 'react';
import { analyticsApi } from '../../api/analytics';
import { dealsApi } from '../../api/crm';
import { parseApiError } from '../../api/errors';
import { useToast } from '../../components/Toast';
import { Button } from '../../components/ui/Button';
import { PageHeader, SearchInput, Toolbar } from '../../components/ui/misc';
import { Spinner } from '../../components/ui/Spinner';
import { useDebounced } from '../../hooks/useListParams';
import { formatDate, formatINR } from '../../lib/format';
import type { BoardColumn, Deal, DealStage } from '../../types';
import { useAuth } from '../auth/AuthContext';
import { STAGES, applyMove, locate } from './board';
import { DealFormModal } from './DealFormModal';

const COLUMN_ACCENT: Record<DealStage, string> = {
  new: 'border-t-sky-400',
  qualified: 'border-t-indigo-400',
  proposal: 'border-t-violet-400',
  negotiation: 'border-t-amber-400',
  won: 'border-t-emerald-500',
  lost: 'border-t-slate-400',
};

interface MoveVars {
  id: number;
  stage: DealStage;
  index: number;
  fromStage: DealStage;
  previous: BoardColumn[] | undefined;
}

export function PipelinePage() {
  const { hasRole } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const debounced = useDebounced(search);
  const boardKey = [dealsApi.key, 'board', debounced];

  const [dragBoard, setDragBoard] = useState<BoardColumn[] | null>(null);
  const [activeId, setActiveId] = useState<number | null>(null);
  const origin = useRef<[DealStage, number] | null>(null);
  const [editing, setEditing] = useState<Deal | null>(null);
  const [creating, setCreating] = useState(false);

  const query = useQuery({
    queryKey: boardKey,
    queryFn: () => dealsApi.board({ search: debounced }),
  });

  // Dragging is turned off while a search filter hides cards: a drop position in a filtered
  // column can't be mapped to the real column order.
  const dragDisabled = debounced.trim() !== '';

  const move = useMutation({
    mutationFn: ({ id, stage, index }: MoveVars) => dealsApi.move(id, stage, index),
    onSuccess: (deal, vars) => {
      if (vars.stage !== vars.fromStage) {
        toast.success(
          `"${deal.title}" moved to ${deal.stage === 'won' ? 'Won 🎉' : capital(deal.stage)}`,
        );
      }
    },
    onError: (err, vars) => {
      queryClient.setQueryData(boardKey, vars.previous); // roll back the optimistic move
      toast.error(`Couldn't move the deal: ${parseApiError(err).message}`);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: [dealsApi.key] });
      queryClient.invalidateQueries({ queryKey: [analyticsApi.key] });
    },
  });

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const columns = dragBoard ?? query.data ?? [];
  const activeDeal = activeId !== null ? findDeal(columns, activeId) : null;

  function stageOf(id: UniqueIdentifier, cols: BoardColumn[]): DealStage | null {
    if (typeof id === 'string' && (STAGES as string[]).includes(id)) return id as DealStage;
    return locate(cols, Number(id))?.[0] ?? null;
  }

  function onDragStart({ active }: DragStartEvent) {
    if (!query.data) return;
    const id = Number(active.id);
    setActiveId(id);
    origin.current = locate(query.data, id);
    setDragBoard(query.data);
  }

  // Live preview while hovering another column.
  function onDragOver({ active, over }: DragOverEvent) {
    if (!over) return;
    setDragBoard((prev) => {
      if (!prev) return prev;
      const from = stageOf(active.id, prev);
      const to = stageOf(over.id, prev);
      if (!from || !to || from === to) return prev;
      const target = prev.find((c) => c.stage === to)!;
      const overIndex = target.deals.findIndex((d) => d.id === Number(over.id));
      return applyMove(
        prev,
        Number(active.id),
        to,
        overIndex === -1 ? target.deals.length : overIndex,
      );
    });
  }

  function onDragEnd({ active, over }: DragEndEvent) {
    const cols = dragBoard;
    const id = Number(active.id);
    setActiveId(null);
    if (!over || !cols || !origin.current) {
      setDragBoard(null);
      return;
    }
    const to = stageOf(over.id, cols);
    let final = cols;
    if (to) {
      const overIndex = cols
        .find((c) => c.stage === to)!
        .deals.findIndex((d) => d.id === Number(over.id));
      if (overIndex !== -1) final = applyMove(cols, id, to, overIndex);
    }
    const landed = locate(final, id);
    const previous = query.data;
    setDragBoard(null);
    if (!landed || (landed[0] === origin.current[0] && landed[1] === origin.current[1])) return;

    void queryClient.cancelQueries({ queryKey: boardKey });
    queryClient.setQueryData(boardKey, final); // optimistic
    move.mutate({ id, stage: landed[0], index: landed[1], fromStage: origin.current[0], previous });
  }

  function onDragCancel() {
    setActiveId(null);
    setDragBoard(null);
  }

  const openTotal = (query.data ?? [])
    .filter((c) => c.stage !== 'won' && c.stage !== 'lost')
    .reduce((sum, c) => sum + Number(c.total_value), 0);

  return (
    <section>
      <PageHeader
        title="Pipeline"
        description={`Drag deals between stages. Open pipeline: ${formatINR(openTotal)}`}
        actions={
          <Button onClick={() => setCreating(true)}>
            <Plus className="size-4" /> New deal
          </Button>
        }
      />
      <Toolbar>
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Search deals, contacts, companies"
        />
        {dragDisabled && <p className="text-xs text-slate-500">Clear the search to drag cards.</p>}
      </Toolbar>

      {query.isLoading ? (
        <div className="flex justify-center py-20">
          <Spinner label="Loading pipeline" />
        </div>
      ) : query.isError ? (
        <p className="py-20 text-center text-sm text-rose-600">
          {parseApiError(query.error).message}
        </p>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={onDragStart}
          onDragOver={onDragOver}
          onDragEnd={onDragEnd}
          onDragCancel={onDragCancel}
        >
          <div className="-mx-4 flex gap-3 overflow-x-auto px-4 pb-4 sm:-mx-6 sm:px-6">
            {columns.map((col) => (
              <Column
                key={col.stage}
                column={col}
                disabled={dragDisabled}
                showOwner={hasRole('admin')}
                onOpen={setEditing}
              />
            ))}
          </div>
          <DragOverlay dropAnimation={null}>
            {activeDeal && <DealCardBody deal={activeDeal} showOwner={hasRole('admin')} lifted />}
          </DragOverlay>
        </DndContext>
      )}

      <DealFormModal
        open={creating || editing !== null}
        deal={editing}
        onClose={() => {
          setCreating(false);
          setEditing(null);
        }}
      />
    </section>
  );
}

function Column({
  column,
  disabled,
  showOwner,
  onOpen,
}: {
  column: BoardColumn;
  disabled: boolean;
  showOwner: boolean;
  onOpen: (deal: Deal) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: column.stage, disabled });
  return (
    <div
      className={`flex w-72 shrink-0 flex-col rounded-xl border border-t-4 border-slate-200 bg-slate-100/70 dark:border-slate-800 dark:bg-slate-900/60 ${COLUMN_ACCENT[column.stage]}`}
      aria-label={`${column.label} column`}
      role="region"
    >
      <div className="flex items-baseline justify-between px-3 pt-3 pb-2">
        <h2 className="text-sm font-semibold">
          {column.label}{' '}
          <span className="ml-1 rounded-full bg-white px-1.5 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
            {column.count}
          </span>
        </h2>
        <span className="text-xs font-medium text-slate-600 tabular-nums dark:text-slate-400">
          {formatINR(column.total_value)}
        </span>
      </div>
      <SortableContext items={column.deals.map((d) => d.id)} strategy={verticalListSortingStrategy}>
        <ul
          ref={setNodeRef}
          className={`flex min-h-24 flex-1 flex-col gap-2 rounded-b-xl px-2 pb-2 transition-colors ${isOver ? 'bg-indigo-50/60 dark:bg-indigo-500/5' : ''}`}
        >
          {column.deals.map((deal) => (
            <SortableCard
              key={deal.id}
              deal={deal}
              disabled={disabled}
              showOwner={showOwner}
              onOpen={onOpen}
            />
          ))}
          {column.deals.length === 0 && (
            <li className="rounded-lg border border-dashed border-slate-300 px-3 py-6 text-center text-xs text-slate-500 dark:border-slate-700">
              Drop deals here
            </li>
          )}
        </ul>
      </SortableContext>
    </div>
  );
}

function SortableCard({
  deal,
  disabled,
  showOwner,
  onOpen,
}: {
  deal: Deal;
  disabled: boolean;
  showOwner: boolean;
  onOpen: (deal: Deal) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: deal.id,
    disabled,
  });
  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={isDragging ? 'opacity-40' : ''}
    >
      <DealCardBody
        deal={deal}
        showOwner={showOwner}
        onOpen={() => onOpen(deal)}
        handleProps={disabled ? undefined : { ...attributes, ...listeners }}
      />
    </li>
  );
}

function DealCardBody({
  deal,
  showOwner,
  onOpen,
  handleProps,
  lifted = false,
}: {
  deal: Deal;
  showOwner: boolean;
  onOpen?: () => void;
  handleProps?: Record<string, unknown>;
  lifted?: boolean;
}) {
  const overdue =
    deal.expected_close_date &&
    deal.stage !== 'won' &&
    deal.stage !== 'lost' &&
    new Date(`${deal.expected_close_date}T23:59:59`) < new Date();
  return (
    <div
      className={`group relative rounded-lg border border-slate-200 bg-white p-3 text-sm shadow-xs dark:border-slate-700 dark:bg-slate-800 ${lifted ? 'rotate-1 shadow-lg ring-2 ring-indigo-400' : 'hover:border-indigo-300 dark:hover:border-indigo-500/60'}`}
    >
      <div className="flex items-start gap-1">
        <button
          type="button"
          onClick={onOpen}
          className="min-w-0 flex-1 text-left font-medium hover:underline focus-visible:outline-2 focus-visible:outline-indigo-500"
        >
          {deal.title}
        </button>
        {handleProps && (
          <button
            type="button"
            aria-label={`Drag ${deal.title}. Press space to pick up, arrows to move.`}
            className="-mr-1 cursor-grab touch-none rounded p-0.5 text-slate-400 hover:bg-slate-100 active:cursor-grabbing dark:hover:bg-slate-700"
            {...handleProps}
          >
            <GripVertical className="size-4" />
          </button>
        )}
      </div>
      <p className="mt-0.5 truncate text-xs text-slate-500">
        {deal.company_name ?? deal.contact_name}
      </p>
      <div className="mt-2 flex items-center justify-between gap-2">
        <span className="font-semibold tabular-nums">{formatINR(deal.value)}</span>
        {deal.expected_close_date && deal.stage !== 'won' && deal.stage !== 'lost' && (
          <span
            className={`inline-flex items-center gap-1 text-xs ${overdue ? 'font-medium text-rose-600 dark:text-rose-400' : 'text-slate-500'}`}
            title="Expected close"
          >
            <CalendarClock className="size-3" aria-hidden />
            {formatDate(deal.expected_close_date)}
          </span>
        )}
      </div>
      {showOwner && deal.owner_name && (
        <p className="mt-1 text-xs text-slate-400">{deal.owner_name}</p>
      )}
    </div>
  );
}

function findDeal(columns: BoardColumn[], id: number): Deal | null {
  for (const col of columns) {
    const deal = col.deals.find((d) => d.id === id);
    if (deal) return deal;
  }
  return null;
}

function capital(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
