import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { DashboardStatsResponse, JobRunSummary, TaskJobStats, TaskSummary, api } from "../api/client";
import { useNotifications } from "../components/NotificationsProvider";
import { getTaskTypeByServiceType } from "../config/taskTypes";

function isManualRecoveryTask(task: TaskSummary) {
  return task.serviceType === "db_restorer" || task.serviceType === "s3_restorer" || task.serviceType === "env_restorer";
}

function formatTaskTriggerMode(task: TaskSummary) {
  if (isManualRecoveryTask(task)) {
    return "Вручную";
  }
  return task.triggerMode === "event_based" ? "По событию" : "По расписанию";
}

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

function formatServiceType(serviceType: TaskSummary["serviceType"]) {
  return getTaskTypeByServiceType(serviceType)?.title ?? serviceType;
}

function formatSize(size: number) {
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KiB`;
  }
  if (size < 1024 * 1024 * 1024) {
    return `${(size / (1024 * 1024)).toFixed(1)} MiB`;
  }
  return `${(size / (1024 * 1024 * 1024)).toFixed(1)} GiB`;
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

function formatJobStatus(status: JobRunSummary["status"]) {
  const labels: Record<JobRunSummary["status"], string> = {
    running: "Выполняется",
    succeeded: "Успешно",
    failed: "Ошибка",
    unknown: "Неизвестно",
  };

  return labels[status];
}

function renderTaskStatsRow(task: TaskJobStats) {
  return (
    <tr key={task.taskId}>
      <td>
        <Link to={`/tasks/${task.taskId}`}>{task.taskName}</Link>
      </td>
      <td>{task.namespace}</td>
      <td>{task.totalRuns}</td>
      <td>{task.manualRuns}</td>
      <td>{task.scheduledRuns}</td>
      <td>{task.eventRuns}</td>
      <td>{task.succeededRuns}</td>
      <td>{task.failedRuns}</td>
      <td>{task.activeRuns}</td>
      <td>{formatDate(task.lastStartedAt)}</td>
    </tr>
  );
}

export function TasksListPage() {
  const { refreshNotifications } = useNotifications();
  const [tasks, setTasks] = useState<TaskSummary[]>([]);
  const [stats, setStats] = useState<DashboardStatsResponse | null>(null);
  const [namespaces, setNamespaces] = useState<string[]>([]);
  const [selectedNamespace, setSelectedNamespace] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [statsError, setStatsError] = useState<string | null>(null);

  async function load() {
    const [tasksResult, namespacesResult, statsResult] = await Promise.allSettled([api.listTasks(), api.listNamespaces(), api.getDashboardStats()]);

    if (tasksResult.status === "rejected") {
      setError(tasksResult.reason instanceof Error ? tasksResult.reason.message : "Не удалось загрузить задачи");
      return;
    }

    if (namespacesResult.status === "rejected") {
      setError(namespacesResult.reason instanceof Error ? namespacesResult.reason.message : "Не удалось загрузить namespace");
      return;
    }

    setTasks(tasksResult.value);
    setNamespaces(namespacesResult.value.namespaces);
    setError(null);

    if (statsResult.status === "fulfilled") {
      setStats(statsResult.value);
      setStatsError(null);
      return;
    }

    setStats(null);
    setStatsError(statsResult.reason instanceof Error ? statsResult.reason.message : "Не удалось загрузить статистику");
  }

  useEffect(() => {
    void load();
  }, []);

  const visibleTasks = selectedNamespace ? tasks.filter((task) => task.namespace === selectedNamespace) : tasks;
  const visibleTaskStats =
    selectedNamespace && stats ? stats.jobs.tasks.filter((task) => task.namespace === selectedNamespace) : stats?.jobs.tasks ?? [];
  const visibleRecentRuns = stats?.jobs.recentRuns.filter((run) => !selectedNamespace || run.namespace === selectedNamespace) ?? [];

  async function handleCreateNamespace() {
    const name = window.prompt("Введите имя namespace");
    const namespace = name?.trim();
    if (!namespace) {
      return;
    }
    try {
      const response = await api.createNamespace({ name: namespace });
      await load();
      setSelectedNamespace(response.name);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось создать namespace");
    }
  }

  async function runAction(action: () => Promise<unknown>) {
    try {
      await action();
      await load();
      await refreshNotifications();
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось выполнить действие");
    }
  }

  return (
    <section className="stack">
      <div className="toolbar">
        <div>
          <h2>Настройка задач оркестрации</h2>
        </div>
        <div className="toolbar-actions">
          <select value={selectedNamespace} onChange={(event) => setSelectedNamespace(event.target.value)}>
            <option value="">Все namespace</option>
            {namespaces.map((namespace) => (
              <option key={namespace} value={namespace}>
                {namespace}
              </option>
            ))}
          </select>
          <button className="button ghost" onClick={() => void handleCreateNamespace()}>
            Создать namespace
          </button>
          <Link className="button primary" to="/tasks/new">
            Создать задачу
          </Link>
        </div>
      </div>

      {error ? <div className="alert">{error}</div> : null}
      {statsError ? <div className="alert">{statsError}</div> : null}

      {stats ? (
        <>
          <div className="stats-grid">
            <article className="card metric-card">
              <p className="eyebrow">Storage</p>
              <h3>{formatSize(stats.storage.totalSize)}</h3>
              <p className="subtle">
                Bucket `{stats.storage.bucketName}` · объектов: {stats.storage.objectCount}
              </p>
            </article>
            <article className="card metric-card">
              <p className="eyebrow">Jobs</p>
              <h3>{stats.jobs.totalRuns}</h3>
              <p className="subtle">Всего запусков по всем задачам</p>
            </article>
            <article className="card metric-card">
              <p className="eyebrow">Triggers</p>
              <h3>
                {stats.jobs.scheduledRuns} / {stats.jobs.eventRuns} / {stats.jobs.manualRuns}
              </h3>
              <p className="subtle">По расписанию / по событию / вручную</p>
            </article>
            <article className="card metric-card">
              <p className="eyebrow">Result</p>
              <h3>
                {stats.jobs.succeededRuns} / {stats.jobs.failedRuns} / {stats.jobs.activeRuns}
              </h3>
              <p className="subtle">Успешно / с ошибкой / выполняется</p>
            </article>
          </div>

          <div className="details-grid dashboard-grid">
            <article className="card table-wrap">
              <div className="toolbar">
                <div>
                  <h3>Статистика по задачам</h3>
                  <p className="subtle">Сколько раз запускались `Job` каждой задачи и каким способом они были созданы.</p>
                </div>
              </div>
              <table>
                <thead>
                  <tr>
                    <th>Задача</th>
                    <th>Namespace</th>
                    <th>Всего</th>
                    <th>Вручную</th>
                    <th>Плановые</th>
                    <th>Событийные</th>
                    <th>Успешно</th>
                    <th>Ошибки</th>
                    <th>Активно</th>
                    <th>Последний запуск</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleTaskStats.map((task) => renderTaskStatsRow(task))}
                  {visibleTaskStats.length === 0 ? (
                    <tr>
                      <td colSpan={10} className="empty-state">
                        Для выбранного namespace статистики запусков пока нет.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </article>

            <article className="card table-wrap">
              <div className="toolbar">
                <div>
                  <h3>Последние запуски</h3>
                  <p className="subtle">Последние `Job`, найденные в Kubernetes по release name задач.</p>
                </div>
              </div>
              <table>
                <thead>
                  <tr>
                    <th>Задача</th>
                    <th>Job</th>
                    <th>Запуск</th>
                    <th>Статус</th>
                    <th>Старт</th>
                    <th>Завершение</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleRecentRuns.map((run) => (
                    <tr key={`${run.namespace}:${run.name}`}>
                      <td>
                        <Link to={`/tasks/${run.taskId}`}>{run.taskName}</Link>
                      </td>
                      <td>{run.name}</td>
                      <td>{formatTriggerType(run.triggerType)}</td>
                      <td>{formatJobStatus(run.status)}</td>
                      <td>{formatDate(run.startedAt)}</td>
                      <td>{formatDate(run.completedAt)}</td>
                    </tr>
                  ))}
                  {visibleRecentRuns.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="empty-state">
                        Запуски `Job` пока не найдены.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </article>
          </div>
        </>
      ) : null}

      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>Название</th>
              <th>Тип</th>
              <th>Namespace</th>
              <th>Включена</th>
              <th>Задеплоена</th>
              <th>Режим</th>
              <th>Расписание</th>
              <th>Последнее применение</th>
              <th>Обновлена</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {visibleTasks.map((task) => (
              <tr key={task.id}>
                <td>
                  <Link to={`/tasks/${task.id}`}>{task.name}</Link>
                </td>
                <td>{formatServiceType(task.serviceType)}</td>
                <td>{task.namespace}</td>
                <td>{formatBoolean(task.enabled)}</td>
                <td>{formatBoolean(task.deployed)}</td>
                <td>{formatTaskTriggerMode(task)}</td>
                <td>{task.schedule ?? "Не используется"}</td>
                <td>{formatApplyStatus(task.lastApplyStatus)}</td>
                <td>{new Date(task.updatedAt).toLocaleString()}</td>
                <td className="row-actions">
                  <Link className="button ghost" to={`/tasks/${task.id}/edit`}>
                    Изменить
                  </Link>
                  <button className="button ghost" onClick={() => void runAction(() => api.refreshTask(String(task.id)))}>
                    Обновить
                  </button>
                  {task.enabled ? (
                    <button className="button danger" onClick={() => void runAction(() => api.disableTask(String(task.id)))}>
                      Выключить
                    </button>
                  ) : (
                    <button className="button primary" onClick={() => void runAction(() => api.enableTask(String(task.id)))}>
                      Включить
                    </button>
                  )}
                  <button
                    className="button ghost"
                    onClick={() => {
                      if (!window.confirm(`Удалить задачу "${task.name}"?`)) {
                        return;
                      }
                      void runAction(() => api.deleteTask(String(task.id)));
                    }}
                  >
                    Удалить
                  </button>
                </td>
              </tr>
            ))}
            {visibleTasks.length === 0 ? (
              <tr>
                <td colSpan={10} className="empty-state">
                  Задачи не найдены.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
