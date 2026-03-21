import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { TaskDetail, api } from "../api/client";
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
            <dt>Расписание</dt>
            <dd>{task.schedule}</dd>
            {task.serviceType === "db_backupper" ? (
              <>
                <dt>Префикс имени файла</dt>
                <dd>{task.dbBackupsFilenamePrefix}</dd>
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
    </section>
  );
}
