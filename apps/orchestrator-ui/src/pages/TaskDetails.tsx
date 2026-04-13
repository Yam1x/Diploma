import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { JobRunSummary, TaskDetail, api } from "../api/client";
import { useNotifications } from "../components/NotificationsProvider";
import { getTaskTypeByServiceType } from "../config/taskTypes";

function formatBoolean(value: boolean) {
  return value ? "Да" : "Нет";
}

function formatApplyStatus(status: string | null) {
  const labels: Record<string, string> = {
    deployed: "Применено",
    failed: "Ошибка",
    disabled: "Отключено",
    missing: "Не найдено",
  };

  if (!status) {
    return "Ожидание";
  }

  return labels[status] ?? status;
}

function formatServiceType(serviceType: TaskDetail["serviceType"]) {
  return getTaskTypeByServiceType(serviceType)?.title ?? serviceType;
}

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString() : "Никогда";
}

function formatTriggerType(triggerType: JobRunSummary["triggerType"]) {
  if (triggerType === "manual") {
    return "Вручную";
  }
  if (triggerType === "event") {
    return "По событию";
  }
  return "По расписанию";
}

function formatTriggerMode(triggerMode: TaskDetail["triggerMode"]) {
  return triggerMode === "event_based" ? "По событию + cron fallback" : "По расписанию";
}

function formatEventWatcherStatus(status: string) {
  const labels: Record<string, string> = {
    scheduled: "Плановый режим",
    disabled: "Выключена",
    waiting_for_baseline: "Инициализация baseline",
    watching: "Отслеживает изменения",
    pending: "Ожидает запуск",
    cooldown: "Cooldown",
    error: "Ошибка",
  };

  return labels[status] ?? status;
}

function formatJobStatus(status: JobRunSummary["status"]) {
  const labels: Record<JobRunSummary["status"], string> = {
    running: "Выполняется",
    succeeded: "Успешно",
    failed: "Ошибка",
    unknown: "Неизвестно",
  };

  return labels[status];
}

function renderTaskParameters(task: TaskDetail) {
  if (task.serviceType === "db_backupper") {
    return (
      <article className="card">
        <h3>Параметры выполнения</h3>
        <dl>
          <dt>Хост базы данных</dt>
          <dd>{task.databaseHost}</dd>
          <dt>Имя базы данных</dt>
          <dd>{task.databaseName}</dd>
          <dt>Пользователь базы данных</dt>
          <dd>{task.databaseUsername}</dd>
          <dt>S3 endpoint</dt>
          <dd>{task.destinationAwsEndpoint}</dd>
          <dt>S3 bucket</dt>
          <dd>{task.destinationAwsBucketName}</dd>
        </dl>
      </article>
    );
  }

  if (task.serviceType === "s3_backupper") {
    return (
      <article className="card">
        <h3>Параметры выполнения</h3>
        <dl>
          <dt>Source S3 endpoint</dt>
          <dd>{task.sourceS3AwsEndpoint}</dd>
          <dt>Source S3 bucket</dt>
          <dd>{task.sourceS3AwsBucketName}</dd>
          <dt>Source S3 subfolder</dt>
          <dd>{task.sourceS3AwsBucketSubfolderName || "Весь bucket"}</dd>
          <dt>Destination S3 endpoint</dt>
          <dd>{task.destinationS3AwsEndpoint}</dd>
          <dt>Destination S3 bucket</dt>
          <dd>{task.destinationS3AwsBucketName}</dd>
        </dl>
      </article>
    );
  }

  return (
    <article className="card">
      <h3>Параметры выполнения</h3>
      <dl>
        <dt>Репозиторий окружения</dt>
        <dd>{task.envRepository}</dd>
        <dt>Путь к Helmfile</dt>
        <dd>{task.pathToHelmfile}</dd>
      </dl>
    </article>
  );
}

export function TaskDetailsPage() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const { refreshNotifications } = useNotifications();
  const [task, setTask] = useState<TaskDetail | null>(null);
  const [jobRuns, setJobRuns] = useState<JobRunSummary[]>([]);
  const [selectedRun, setSelectedRun] = useState<JobRunSummary | null>(null);
  const [selectedRunLogs, setSelectedRunLogs] = useState("");
  const [logsLoading, setLogsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [logsError, setLogsError] = useState<string | null>(null);

  async function load() {
    if (!taskId) {
      return;
    }
    try {
      const [detail, runsResponse] = await Promise.all([api.getTask(taskId), api.listTaskJobRuns(taskId)]);
      setTask(detail);
      setJobRuns(runsResponse.runs);
      setSelectedRun((current) => (current ? runsResponse.runs.find((run) => run.id === current.id) ?? null : null));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить задачу");
    }
  }

  useEffect(() => {
    void load();
  }, [taskId]);

  async function run(action: () => Promise<TaskDetail>) {
    try {
      await action();
      await load();
      await refreshNotifications();
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось выполнить действие");
    }
  }

  async function handleDelete() {
    if (!task) {
      return;
    }
    if (!window.confirm(`Удалить задачу "${task.name}"?`)) {
      return;
    }
    try {
      await api.deleteTask(String(task.id));
      setError(null);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось удалить задачу");
    }
  }

  async function handleLoadLogs(runItem: JobRunSummary) {
    if (!taskId) {
      return;
    }
    try {
      setSelectedRun(runItem);
      setLogsError(null);
      setLogsLoading(true);
      const response = await api.getTaskJobRunLogs(taskId, runItem.id);
      setSelectedRun(response.run);
      setSelectedRunLogs(response.logs);
    } catch (err) {
      setSelectedRun(runItem);
      setSelectedRunLogs("");
      setLogsError(err instanceof Error ? err.message : "Не удалось загрузить логи запуска");
    } finally {
      setLogsLoading(false);
    }
  }

  if (!task) {
    return <section className="stack">{error ? <div className="alert">{error}</div> : <p>Загрузка...</p>}</section>;
  }

  return (
    <section className="stack">
      <div className="toolbar">
        <div>
          <h2>{task.name}</h2>
          <p className="subtle">Текущий релиз: `{task.releaseName}` в namespace `{task.namespace}`.</p>
        </div>
        <div className="toolbar-actions">
          <Link className="button ghost" to={`/tasks/${task.id}/edit`}>
            Изменить
          </Link>
          <button className="button ghost" onClick={() => void run(() => api.refreshTask(String(task.id)))}>
            Обновить
          </button>
          <button className="button primary" onClick={() => void run(() => api.runTask(String(task.id)))} disabled={!task.enabled}>
            Запустить сейчас
          </button>
          {task.enabled ? (
            <button className="button danger" onClick={() => void run(() => api.disableTask(String(task.id)))}>
              Выключить
            </button>
          ) : (
            <button className="button primary" onClick={() => void run(() => api.enableTask(String(task.id)))}>
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
          <h3>Желаемое состояние</h3>
          <dl>
            <dt>Включена</dt>
            <dd>{formatBoolean(task.enabled)}</dd>
            <dt>Тип сервиса</dt>
            <dd>{formatServiceType(task.serviceType)}</dd>
            <dt>Режим запуска</dt>
            <dd>{formatTriggerMode(task.triggerMode)}</dd>
            <dt>Расписание</dt>
            <dd>{task.triggerMode === "event_based" ? `${task.schedule} (fallback)` : task.schedule}</dd>
            {task.serviceType === "db_backupper" ? (
              <>
                <dt>Префикс имени файла</dt>
                <dd>{task.dbBackupsFilenamePrefix}</dd>
                <dt>Event watcher</dt>
                <dd>{formatEventWatcherStatus(task.eventWatcherStatus)}</dd>
                <dt>Последнее событие</dt>
                <dd>{formatDate(task.lastEventDetectedAt)}</dd>
                <dt>Последний event backup</dt>
                <dd>{formatDate(task.lastEventTriggeredAt)}</dd>
                <dt>Сообщение watcher</dt>
                <dd>{task.lastEventMessage ?? "Нет сообщений"}</dd>
              </>
            ) : task.serviceType === "s3_backupper" ? (
              <>
                <dt>Префикс имени архива</dt>
                <dd>{task.s3BackupsFilenamePrefix}</dd>
              </>
            ) : null}
          </dl>
        </article>
        <article className="card">
          <h3>Состояние деплоя</h3>
          <dl>
            <dt>Задеплоена</dt>
            <dd>{formatBoolean(task.deployed)}</dd>
            <dt>Статус последнего применения</dt>
            <dd>{formatApplyStatus(task.lastApplyStatus)}</dd>
            <dt>Последнее применение</dt>
            <dd>{task.lastAppliedAt ? new Date(task.lastAppliedAt).toLocaleString() : "Никогда"}</dd>
            <dt>Последнее сообщение</dt>
            <dd>{task.lastApplyMessage ?? "Сообщений пока нет"}</dd>
          </dl>
        </article>
        {renderTaskParameters(task)}
      </div>

      <article className="card table-wrap">
        <div className="toolbar">
          <div>
            <h3>Последние запуски</h3>
            <p className="subtle">Список последних `Job` этой задачи с доступом к их логам.</p>
          </div>
        </div>
        <table>
          <thead>
            <tr>
              <th>Job</th>
              <th>Запуск</th>
              <th>Статус</th>
              <th>Старт</th>
              <th>Завершение</th>
              <th>Последний sync</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {jobRuns.map((runItem) => (
              <tr key={runItem.id}>
                <td>{runItem.name}</td>
                <td>{formatTriggerType(runItem.triggerType)}</td>
                <td>{formatJobStatus(runItem.status)}</td>
                <td>{formatDate(runItem.startedAt)}</td>
                <td>{formatDate(runItem.completedAt)}</td>
                <td>{formatDate(runItem.lastSeenAt)}</td>
                <td className="row-actions">
                  <button className="button ghost" onClick={() => void handleLoadLogs(runItem)} disabled={logsLoading && selectedRun?.id === runItem.id}>
                    {logsLoading && selectedRun?.id === runItem.id ? "Загружаем..." : runItem.hasLogs ? "Логи" : "Получить логи"}
                  </button>
                </td>
              </tr>
            ))}
            {jobRuns.length === 0 ? (
              <tr>
                <td colSpan={7} className="empty-state">
                  Запуски `Job` для этой задачи пока не найдены.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </article>

      {selectedRun ? (
        <article className="card">
          <div className="toolbar">
            <div>
              <h3>Логи запуска</h3>
              <p className="subtle">
                `{selectedRun.name}` · {formatJobStatus(selectedRun.status)} · {formatDate(selectedRun.startedAt)}
              </p>
            </div>
          </div>
          {logsError ? <div className="alert">{logsError}</div> : null}
          <pre className="log-output">{selectedRunLogs || (logsLoading ? "Загружаем логи..." : "Логи для этого запуска пока недоступны.")}</pre>
        </article>
      ) : null}
    </section>
  );
}
