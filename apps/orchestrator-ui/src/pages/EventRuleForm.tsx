import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { BackupEventRulePayload, TaskSummary, api } from "../api/client";

function buildTaskOptionLabel(task: TaskSummary) {
  return `${task.name} · ${task.namespace} · ${task.releaseName}`;
}

function isCompatibleTask(task: TaskSummary, serviceType: TaskSummary["serviceType"]) {
  return task.serviceType === serviceType && task.triggerMode === "event_based" && task.enabled && task.deployed;
}

export function EventRuleFormPage() {
  const navigate = useNavigate();
  const { ruleId } = useParams();
  const isEditMode = Boolean(ruleId);
  const [value, setValue] = useState<BackupEventRulePayload>({
    name: "",
    enabled: true,
    dbTaskId: 0,
    s3TaskId: 0,
  });
  const [tasks, setTasks] = useState<TaskSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [taskList, detail] = await Promise.all([api.listTasks(), ruleId ? api.getEventRule(ruleId) : Promise.resolve(null)]);
        setTasks(taskList);
        if (detail) {
          setValue({
            name: detail.name,
            enabled: detail.enabled,
            dbTaskId: detail.dbTaskId,
            s3TaskId: detail.s3TaskId,
          });
        }
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Не удалось загрузить форму event rule");
      }
    }

    void load();
  }, [ruleId]);

  const dbTasks = useMemo(() => tasks.filter((task) => isCompatibleTask(task, "db_backupper")), [tasks]);
  const s3Tasks = useMemo(() => tasks.filter((task) => isCompatibleTask(task, "s3_backupper")), [tasks]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();

    try {
      if (ruleId) {
        await api.updateEventRule(ruleId, value);
        navigate(`/event-rules/${ruleId}`);
      } else {
        const rule = await api.createEventRule(value);
        navigate(`/event-rules/${rule.id}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сохранить event rule");
    }
  }

  return (
    <section className="stack">
      <div className="toolbar">
        <div>
          <h2>{ruleId ? "Редактирование event rule" : "Создание event rule"}</h2>
          <p className="subtle">Правило запускает оба backup job, когда DB и S3 изменились в одном watcher poll.</p>
        </div>
        <Link className="button ghost" to={ruleId ? `/event-rules/${ruleId}` : "/event-rules"}>
          Отмена
        </Link>
      </div>

      {error ? <div className="alert">{error}</div> : null}

      <form className="card form-grid" onSubmit={(event) => void handleSubmit(event)}>
        <label>
          <span>Название</span>
          <input value={value.name} onChange={(event) => setValue({ ...value, name: event.target.value })} required />
        </label>
        <label>
          <span>DB task</span>
          <small className="field-help">Доступны только включенные и deployed `db_backupper` в event mode.</small>
          <select value={value.dbTaskId || ""} onChange={(event) => setValue({ ...value, dbTaskId: Number(event.target.value) })} required>
            <option value="">Выберите DB task</option>
            {dbTasks.map((task) => (
              <option key={task.id} value={task.id}>
                {buildTaskOptionLabel(task)}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>S3 task</span>
          <small className="field-help">Доступны только включенные и deployed `s3_backupper` в event mode.</small>
          <select value={value.s3TaskId || ""} onChange={(event) => setValue({ ...value, s3TaskId: Number(event.target.value) })} required>
            <option value="">Выберите S3 task</option>
            {s3Tasks.map((task) => (
              <option key={task.id} value={task.id}>
                {buildTaskOptionLabel(task)}
              </option>
            ))}
          </select>
        </label>
        <label className="toggle">
          <input type="checkbox" checked={value.enabled} onChange={(event) => setValue({ ...value, enabled: event.target.checked })} />
          <span>Включить event rule</span>
        </label>
        <div className="toolbar-actions">
          <button className="button primary" type="submit">
            Сохранить event rule
          </button>
        </div>
      </form>
    </section>
  );
}
