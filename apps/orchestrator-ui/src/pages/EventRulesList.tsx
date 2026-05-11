import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { BackupEventRuleSummary, api } from "../api/client";

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

export function EventRulesListPage() {
  const [rules, setRules] = useState<BackupEventRuleSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api
      .listEventRules()
      .then((response) => {
        setRules(response);
        setError(null);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Не удалось загрузить event rules");
      });
  }, []);

  return (
    <section className="stack">
      <div className="toolbar">
        <div>
          <h2>Event Rules</h2>
        </div>
        <div className="toolbar-actions">
          <Link className="button primary" to="/event-rules/new">
            Новое правило
          </Link>
        </div>
      </div>

      {error ? <div className="alert">{error}</div> : null}

      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>Название</th>
              <th>Namespace</th>
              <th>DB backup</th>
              <th>S3 backup</th>
              <th>Включено</th>
              <th>Watcher</th>
              <th>Последний combined run</th>
              <th>Обновлено</th>
            </tr>
          </thead>
          <tbody>
            {rules.map((rule) => (
              <tr key={rule.id}>
                <td>
                  <Link to={`/event-rules/${rule.id}`}>{rule.name}</Link>
                </td>
                <td>{rule.namespace}</td>
                <td>{rule.dbName}</td>
                <td>{rule.s3Name}</td>
                <td>{formatBoolean(rule.enabled)}</td>
                <td>{formatEventWatcherStatus(rule.eventWatcherStatus)}</td>
                <td>{formatDate(rule.lastTriggeredAt)}</td>
                <td>{formatDate(rule.updatedAt)}</td>
              </tr>
            ))}
            {rules.length === 0 ? (
              <tr>
                <td colSpan={8} className="empty-state">
                  Event rules пока не созданы.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
