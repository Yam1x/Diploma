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
        setError(err instanceof Error ? err.message : "РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РіСЂСѓР·РёС‚СЊ С„РѕСЂРјСѓ event rule");
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
      setError(err instanceof Error ? err.message : "РќРµ СѓРґР°Р»РѕСЃСЊ СЃРѕС…СЂР°РЅРёС‚СЊ event rule");
    }
  }

  return (
    <section className="stack">
      <div className="toolbar">
        <div>
          <h2>{ruleId ? "Р РµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ event rule" : "РЎРѕР·РґР°РЅРёРµ event rule"}</h2>
          <p className="subtle">РџСЂР°РІРёР»Рѕ Р·Р°РїСѓСЃРєР°РµС‚ РѕР±Р° backup job, РєРѕРіРґР° DB Рё S3 РёР·РјРµРЅРёР»РёСЃСЊ РІ РѕРґРЅРѕРј watcher poll.</p>
        </div>
        <Link className="button ghost" to={ruleId ? `/event-rules/${ruleId}` : "/event-rules"}>
          РћС‚РјРµРЅР°
        </Link>
      </div>

      {error ? <div className="alert">{error}</div> : null}

      <form className="card form-grid" onSubmit={(event) => void handleSubmit(event)}>
        <label>
          <span>РќР°Р·РІР°РЅРёРµ</span>
          <input value={value.name} onChange={(event) => setValue({ ...value, name: event.target.value })} required />
        </label>
        <label>
          <span>DB task</span>
          <small className="field-help">Р”РѕСЃС‚СѓРїРЅС‹ С‚РѕР»СЊРєРѕ РІРєР»СЋС‡РµРЅРЅС‹Рµ Рё deployed `db_backupper` РІ event mode.</small>
          <select value={value.dbTaskId || ""} onChange={(event) => setValue({ ...value, dbTaskId: Number(event.target.value) })} required>
            <option value="">Р’С‹Р±РµСЂРёС‚Рµ DB task</option>
            {dbTasks.map((task) => (
              <option key={task.id} value={task.id}>
                {buildTaskOptionLabel(task)}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>S3 task</span>
          <small className="field-help">Р”РѕСЃС‚СѓРїРЅС‹ С‚РѕР»СЊРєРѕ РІРєР»СЋС‡РµРЅРЅС‹Рµ Рё deployed `s3_backupper` РІ event mode.</small>
          <select value={value.s3TaskId || ""} onChange={(event) => setValue({ ...value, s3TaskId: Number(event.target.value) })} required>
            <option value="">Р’С‹Р±РµСЂРёС‚Рµ S3 task</option>
            {s3Tasks.map((task) => (
              <option key={task.id} value={task.id}>
                {buildTaskOptionLabel(task)}
              </option>
            ))}
          </select>
        </label>
        <label className="toggle">
          <input type="checkbox" checked={value.enabled} onChange={(event) => setValue({ ...value, enabled: event.target.checked })} />
          <span>Р’РєР»СЋС‡РёС‚СЊ event rule</span>
        </label>
        <div className="toolbar-actions">
          <button className="button primary" type="submit">
            РЎРѕС…СЂР°РЅРёС‚СЊ event rule
          </button>
        </div>
      </form>
    </section>
  );
}
