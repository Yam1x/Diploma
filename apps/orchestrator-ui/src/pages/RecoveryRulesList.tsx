import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { RecoveryEventRuleSummary, api } from "../api/client";

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
    watching: "Отслеживает target-state",
    restoring: "Восстановление идёт",
    cooldown: "Cooldown",
    error: "Ошибка",
  };

  return labels[status] ?? status;
}

export function RecoveryRulesListPage() {
  const [rules, setRules] = useState<RecoveryEventRuleSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api
      .listRecoveryRules()
      .then((response) => {
        setRules(response);
        setError(null);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Не удалось загрузить recovery rules");
      });
  }, []);

  return (
    <section className="stack">
      <div className="toolbar">
        <div>
          <h2>Recovery Rules</h2>
          <p className="subtle">Настраивайте event-based восстановление для пары `db_restorer` + `s3_restorer`.</p>
        </div>
        <div className="toolbar-actions">
          <Link className="button primary" to="/recovery-rules/new">
            Новое recovery rule
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
              <th>DB restore</th>
              <th>S3 restore</th>
              <th>Включено</th>
              <th>Watcher</th>
              <th>Последний DB restore</th>
              <th>Последний S3 restore</th>
              <th>Обновлено</th>
            </tr>
          </thead>
          <tbody>
            {rules.map((rule) => (
              <tr key={rule.id}>
                <td>
                  <Link to={`/recovery-rules/${rule.id}`}>{rule.name}</Link>
                </td>
                <td>{rule.namespace}</td>
                <td>{rule.dbName}</td>
                <td>{rule.s3Name}</td>
                <td>{formatBoolean(rule.enabled)}</td>
                <td>{formatEventWatcherStatus(rule.eventWatcherStatus)}</td>
                <td>{formatDate(rule.lastDbTriggeredAt)}</td>
                <td>{formatDate(rule.lastS3TriggeredAt)}</td>
                <td>{formatDate(rule.updatedAt)}</td>
              </tr>
            ))}
            {rules.length === 0 ? (
              <tr>
                <td colSpan={9} className="empty-state">
                  Recovery rules пока не созданы.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
