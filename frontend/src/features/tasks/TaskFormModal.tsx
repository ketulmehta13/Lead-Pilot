import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { tasksApi } from '../../api/crm';
import { ContactSelect } from '../../components/ContactSelect';
import { useToast } from '../../components/Toast';
import { Button } from '../../components/ui/Button';
import { SelectField, TextAreaField, TextField } from '../../components/ui/Field';
import { Modal } from '../../components/ui/Modal';
import { applyServerErrors } from '../../lib/forms';
import { TASK_PRIORITY_OPTIONS, TASK_STATUS_OPTIONS } from '../../lib/options';
import type { Task, TaskPriority, TaskStatus } from '../../types';

const taskSchema = z.object({
  title: z.string().trim().min(1, 'Title is required').max(200),
  description: z.string().max(5000),
  due_date: z.string(),
  priority: z.string().min(1),
  status: z.string().min(1),
  contact: z.string(),
});
type FormValues = z.infer<typeof taskSchema>;
const FIELDS = ['title', 'description', 'due_date', 'priority', 'status', 'contact'] as const;
const empty: FormValues = {
  title: '',
  description: '',
  due_date: '',
  priority: 'medium',
  status: 'todo',
  contact: '',
};

export function TaskFormModal({
  open,
  task,
  onClose,
}: {
  open: boolean;
  task?: Task | null;
  onClose: () => void;
}) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { register, handleSubmit, reset, setError, formState } = useForm<FormValues>({
    resolver: zodResolver(taskSchema),
    defaultValues: empty,
  });

  useEffect(() => {
    if (!open) return;
    reset(
      task
        ? {
            title: task.title,
            description: task.description,
            due_date: task.due_date ?? '',
            priority: task.priority,
            status: task.status,
            contact: task.contact ? String(task.contact) : '',
          }
        : empty,
    );
  }, [open, task, reset]);

  const mutation = useMutation({
    mutationFn: (v: FormValues) => {
      const payload = {
        title: v.title,
        description: v.description,
        due_date: v.due_date || null,
        priority: v.priority as TaskPriority,
        status: v.status as TaskStatus,
        contact: v.contact ? Number(v.contact) : null,
      };
      return task ? tasksApi.update(task.id, payload) : tasksApi.create(payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [tasksApi.key] });
      toast.success(task ? 'Task updated' : 'Task created');
      onClose();
    },
    onError: (err) => toast.error(applyServerErrors(err, setError, FIELDS)),
  });

  const e = formState.errors;
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={task ? 'Edit task' : 'New task'}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="task-form" loading={mutation.isPending}>
            {task ? 'Save changes' : 'Create task'}
          </Button>
        </>
      }
    >
      <form
        id="task-form"
        noValidate
        onSubmit={handleSubmit((v) => mutation.mutate(v))}
        className="grid gap-4 sm:grid-cols-3"
      >
        <div className="sm:col-span-3">
          <TextField label="Title" required error={e.title?.message} {...register('title')} />
        </div>
        <TextField
          label="Due date"
          type="date"
          error={e.due_date?.message}
          {...register('due_date')}
        />
        <SelectField label="Priority" options={TASK_PRIORITY_OPTIONS} {...register('priority')} />
        <SelectField label="Status" options={TASK_STATUS_OPTIONS} {...register('status')} />
        <div className="sm:col-span-3">
          <ContactSelect
            registration={register('contact')}
            error={e.contact?.message}
            emptyLabel="No contact"
            current={
              task?.contact
                ? { id: task.contact, name: task.contact_name ?? 'Current contact' }
                : null
            }
          />
        </div>
        <div className="sm:col-span-3">
          <TextAreaField
            label="Description"
            rows={3}
            error={e.description?.message}
            {...register('description')}
          />
        </div>
      </form>
    </Modal>
  );
}
