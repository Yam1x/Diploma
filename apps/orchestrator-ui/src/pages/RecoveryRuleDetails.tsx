import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { RecoveryEventRuleDetail, api } from "../api/client";

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
    watching: "Отслеживает target-state",
    restoring: "Восстановление идёт",
    cooldown: "Cooldown",
    error: "Ошибка",
  };

  return labels[status] ?? status;
}

export function RecoveryRuleDetailsPage() {
  const { ruleId } = useParams();
  const navigate = useNavigate();
  const [rule, setRule] = useState<RecoveryEventRuleDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!ruleId) {
      return;
    }
    try {
      const detail = await api.getRecoveryRule(ruleId);
      setRule(detail);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить recovery rule");
    }
  }

  useEffect(() => {
    void load();
  }, [ruleId]);

  async function runAction(action: () => Promise<RecoveryEventRuleDetail | void>) {
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
    if (!window.confirm(`Удалить recovery rule "${rule.name}"?`)) {
      return;
    }
    try {
      await api.deleteRecoveryRule(ruleId);
      navigate("/recovery-rules");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось удалить recovery rule");
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
          <p className="subtle">Recovery rule управляет парой managed restore service в namespace `{rule.namespace}`.</p>
        </div>
        <div className="toolbar-actions">
          <Link className="button ghost" to={`/recovery-rules/${rule.id}/edit`}>
            Изменить
          </Link>
          <button className="button primary" onClick={() => void runAction(() => api.runRecoveryRule(String(rule.id)))}>
            Восстановить сейчас
          </button>
          {rule.enabled ? (
            <button className="button danger" onClick={() => void runAction(() => api.disableRecoveryRule(String(rule.id)))}>
              Выключить
            </button>
          ) : (
            <button className="button primary" onClick={() => void runAction(() => api.enableRecoveryRule(String(rule.id)))}>
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
            <dt>DB restore</dt>
            <dd>{rule.db.name}</dd>
            <dt>S3 restore</dt>
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
            <dt>DB пустая</dt>
            <dd>{formatDate(rule.lastDbEmptyAt)}</dd>
            <dt>S3 пустой</dt>
            <dd>{formatDate(rule.lastS3EmptyAt)}</dd>
            <dt>Последний DB restore</dt>
            <dd>{formatDate(rule.lastDbTriggeredAt)}</dd>
            <dt>Последний S3 restore</dt>
            <dd>{formatDate(rule.lastS3TriggeredAt)}</dd>
            <dt>Последняя ошибка</dt>
            <dd>{rule.lastErrorMessage ?? "Нет"}</dd>
          </dl>
        </article>
      </div>

      <div className="details-grid">
        <article className="card">
          <h3>DB restore config</h3>
          <dl>
            <dt>Backup prefix</dt>
            <dd>{rule.db.dbBackupsFilenamePrefix}</dd>
            <dt>Source endpoint</dt>
            <dd>{rule.db.sourceAwsEndpoint}</dd>
            <dt>Source bucket</dt>
            <dd>{rule.db.sourceAwsBucketName}</dd>
            <dt>Source access key</dt>
            <dd>{rule.db.sourceAwsAccessKeyId}</dd>
            <dt>Target DB host</dt>
            <dd>{rule.db.targetDatabaseHost}</dd>
            <dt>Target DB name</dt>
            <dd>{rule.db.targetDatabaseName}</dd>
            <dt>Target DB user</dt>
            <dd>{rule.db.targetDatabaseUsername}</dd>
            <dt>Source secret</dt>
            <dd>{formatConfigured(rule.db.hasSourceAwsSecretAccessKey)}</dd>
            <dt>Target DB password</dt>
            <dd>{formatConfigured(rule.db.hasTargetDatabasePassword)}</dd>
          </dl>
        </article>
        <article className="card">
          <h3>S3 restore config</h3>
          <dl>
            <dt>Backup prefix</dt>
            <dd>{rule.s3.s3BackupsFilenamePrefix}</dd>
            <dt>Source endpoint</dt>
            <dd>{rule.s3.sourceS3AwsEndpoint}</dd>
            <dt>Source bucket</dt>
            <dd>{rule.s3.sourceS3AwsBucketName}</dd>
            <dt>Source access key</dt>
            <dd>{rule.s3.sourceS3AwsAccessKeyId}</dd>
            <dt>Target endpoint</dt>
            <dd>{rule.s3.targetS3AwsEndpoint}</dd>
            <dt>Target bucket</dt>
            <dd>{rule.s3.targetS3AwsBucketName}</dd>
            <dt>Target subfolder</dt>
            <dd>{rule.s3.targetS3AwsBucketSubfolderName || "Весь bucket"}</dd>
            <dt>Target access key</dt>
            <dd>{rule.s3.targetS3AwsAccessKeyId}</dd>
            <dt>Source secret</dt>
            <dd>{formatConfigured(rule.s3.hasSourceS3AwsSecretAccessKey)}</dd>
            <dt>Target secret</dt>
            <dd>{formatConfigured(rule.s3.hasTargetS3AwsSecretAccessKey)}</dd>
          </dl>
        </article>
      </div>
    </section>
  );
}
