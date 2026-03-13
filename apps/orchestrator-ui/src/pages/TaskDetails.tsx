import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, TaskDetail } from "../api/client";
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

function formatServiceType(serviceType: string) {
  return getTaskTypeByServiceType(serviceType)?.title ?? serviceType;
}

export function TaskDetailsPage() {
  const { taskId } = useParams();
  const [task, setTask] = useState<TaskDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!taskId) {
      return;
    }
    try {
      const detail = await api.getTask(taskId);
      setTask(detail);
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
      const detail = await action();
      setTask(detail);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось выполнить действие");
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
          {task.enabled ? (
            <button className="button danger" onClick={() => void run(() => api.disableTask(String(task.id))) }>
              Выключить
            </button>
          ) : (
            <button className="button primary" onClick={() => void run(() => api.enableTask(String(task.id)))}>
              Включить
            </button>
          )}
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
            <dt>Расписание</dt>
            <dd>{task.schedule}</dd>
            <dt>Префикс имени файла</dt>
            <dd>{task.dbBackupsFilenamePrefix}</dd>
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
      </div>
    </section>
  );
}
