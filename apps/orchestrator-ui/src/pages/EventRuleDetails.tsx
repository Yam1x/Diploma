import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { BackupEventRuleDetail, api } from "../api/client";

function formatBoolean(value: boolean) {
  return value ? "Да" : "Нет";
}

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString() : "Никогда";
}

function formatConfigured(value: boolean) {
  return value ? "Настроено" : "Нет";
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
          <p className="subtle">Event rule владеет парой managed backup service в namespace `{rule.namespace}`.</p>
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
            <dt>Namespace</dt>
            <dd>{rule.namespace}</dd>
            <dt>DB backup</dt>
            <dd>{rule.db.name}</dd>
            <dt>S3 backup</dt>
            <dd>{rule.s3.name}</dd>
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

      <div className="details-grid">
        <article className="card">
          <h3>DB backup config</h3>
          <dl>
            <dt>Хост базы данных</dt>
            <dd>{rule.db.databaseHost}</dd>
            <dt>Имя базы данных</dt>
            <dd>{rule.db.databaseName}</dd>
            <dt>Пользователь</dt>
            <dd>{rule.db.databaseUsername}</dd>
            <dt>Префикс файла</dt>
            <dd>{rule.db.dbBackupsFilenamePrefix}</dd>
            <dt>Destination endpoint</dt>
            <dd>{rule.db.destinationAwsEndpoint}</dd>
            <dt>Destination bucket</dt>
            <dd>{rule.db.destinationAwsBucketName}</dd>
            <dt>Destination access key</dt>
            <dd>{rule.db.destinationAwsAccessKeyId}</dd>
            <dt>DB password</dt>
            <dd>{formatConfigured(rule.db.hasDatabasePassword)}</dd>
            <dt>Destination secret</dt>
            <dd>{formatConfigured(rule.db.hasDestinationAwsSecretAccessKey)}</dd>
          </dl>
        </article>
        <article className="card">
          <h3>S3 backup config</h3>
          <dl>
            <dt>Source endpoint</dt>
            <dd>{rule.s3.sourceS3AwsEndpoint}</dd>
            <dt>Source bucket</dt>
            <dd>{rule.s3.sourceS3AwsBucketName}</dd>
            <dt>Source subfolder</dt>
            <dd>{rule.s3.sourceS3AwsBucketSubfolderName || "Весь bucket"}</dd>
            <dt>Destination endpoint</dt>
            <dd>{rule.s3.destinationS3AwsEndpoint}</dd>
            <dt>Destination bucket</dt>
            <dd>{rule.s3.destinationS3AwsBucketName}</dd>
            <dt>Source access key</dt>
            <dd>{rule.s3.sourceS3AwsAccessKeyId}</dd>
            <dt>Destination access key</dt>
            <dd>{rule.s3.destinationS3AwsAccessKeyId}</dd>
            <dt>Source secret</dt>
            <dd>{formatConfigured(rule.s3.hasSourceS3AwsSecretAccessKey)}</dd>
            <dt>Destination secret</dt>
            <dd>{formatConfigured(rule.s3.hasDestinationS3AwsSecretAccessKey)}</dd>
          </dl>
        </article>
      </div>
    </section>
  );
}
