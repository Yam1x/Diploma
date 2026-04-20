import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { BackupEventRuleDetail, api } from "../api/client";

function formatBoolean(value: boolean) {
  return value ? "Да" : "Нет";
}

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString() : "Никогда";
}

function formatEventWatcherStatus(status: string) {
  const labels: Record<string, string> = {
    disabled: "Выключено",
    waiting_for_baseline: "Инициализация baseline",
    watching: "Отслеживает изменения",
    cooldown: "Cooldown",
    error: "Ошибка",
  };

  return labels[status] ?? status;
}

export function EventRuleDetailsPage() {
  const { ruleId } = useParams();
  const navigate = useNavigate();
  const [rule, setRule] = useState<BackupEventRuleDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!ruleId) {
      return;
    }
    try {
      const detail = await api.getEventRule(ruleId);
      setRule(detail);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить event rule");
    }
  }

  useEffect(() => {
    void load();
  }, [ruleId]);

  async function runAction(action: () => Promise<BackupEventRuleDetail | void>) {
    try {
      await action();
      await load();
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось выполнить действие");
    }
  }

  async function handleDelete() {
    if (!ruleId || !rule) {
      return;
    }
    if (!window.confirm(`Удалить event rule "${rule.name}"?`)) {
      return;
    }
    try {
      await api.deleteEventRule(ruleId);
      navigate("/event-rules");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось удалить event rule");
    }
  }

  if (!rule) {
    return <section className="stack">{error ? <div className="alert">{error}</div> : <p>Загрузка...</p>}</section>;
  }

  return (
    <section className="stack">
      <div className="toolbar">
        <div>
          <h2>{rule.name}</h2>
          <p className="subtle">Combined event rule для парного backup DB + S3.</p>
        </div>
        <div className="toolbar-actions">
          <Link className="button ghost" to={`/event-rules/${rule.id}/edit`}>
            Изменить
          </Link>
          <button className="button primary" onClick={() => void runAction(() => api.runEventRule(String(rule.id)))}>
            Запустить сейчас
          </button>
          {rule.enabled ? (
            <button className="button danger" onClick={() => void runAction(() => api.disableEventRule(String(rule.id)))}>
              Выключить
            </button>
          ) : (
            <button className="button primary" onClick={() => void runAction(() => api.enableEventRule(String(rule.id)))}>
              Включить
            </button>
          )}
          <button className="button ghost" onClick={() => void handleDelete()}>
            Удалить
          </button>
        </div>
      </div>

      {error ? <div className="alert">{error}</div> : null}

      <div className="details-grid">
        <article className="card">
          <h3>Состояние</h3>
          <dl>
            <dt>Включено</dt>
            <dd>{formatBoolean(rule.enabled)}</dd>
            <dt>DB task</dt>
            <dd>{rule.dbTaskName}</dd>
            <dt>S3 task</dt>
            <dd>{rule.s3TaskName}</dd>
            <dt>Watcher</dt>
            <dd>{formatEventWatcherStatus(rule.eventWatcherStatus)}</dd>
          </dl>
        </article>
        <article className="card">
          <h3>События watcher</h3>
          <dl>
            <dt>Последний poll</dt>
            <dd>{formatDate(rule.lastPolledAt)}</dd>
            <dt>DB change</dt>
            <dd>{formatDate(rule.lastDbChangeAt)}</dd>
            <dt>S3 change</dt>
            <dd>{formatDate(rule.lastS3ChangeAt)}</dd>
            <dt>Combined run</dt>
            <dd>{formatDate(rule.lastTriggeredAt)}</dd>
            <dt>Последняя ошибка</dt>
            <dd>{rule.lastErrorMessage ?? "Нет"}</dd>
          </dl>
        </article>
      </div>
    </section>
  );
}
