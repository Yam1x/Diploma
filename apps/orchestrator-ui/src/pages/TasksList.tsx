import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, TaskSummary } from "../api/client";

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

export function TasksListPage() {
  const [tasks, setTasks] = useState<TaskSummary[]>([]);
  const [namespaces, setNamespaces] = useState<string[]>([]);
  const [selectedNamespace, setSelectedNamespace] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const [taskList, namespaceResponse] = await Promise.all([api.listTasks(), api.listNamespaces()]);
      setTasks(taskList);
      setNamespaces(namespaceResponse.namespaces);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить задачи");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const visibleTasks = selectedNamespace ? tasks.filter((task) => task.namespace === selectedNamespace) : tasks;
  const enabledCount = tasks.filter((task) => task.enabled).length;
  const deployedCount = tasks.filter((task) => task.deployed).length;
  const failedCount = tasks.filter((task) => task.lastApplyStatus === "failed").length;

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
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось выполнить действие");
    }
  }

  return (
    <section className="stack">
      <div className="metrics-grid">
        <article className="metric-card">
          <span className="metric-label">Всего задач</span>
          <strong>{tasks.length}</strong>
          <p className="subtle">Все сохранённые конфигурации оркестратора.</p>
        </article>
        <article className="metric-card">
          <span className="metric-label">Активные</span>
          <strong>{enabledCount}</strong>
          <p className="subtle">Задачи с включённым желаемым состоянием.</p>
        </article>
        <article className="metric-card">
          <span className="metric-label">Задеплоены</span>
          <strong>{deployedCount}</strong>
          <p className="subtle">Релизы, успешно присутствующие в кластере.</p>
        </article>
        <article className="metric-card">
          <span className="metric-label">С ошибкой</span>
          <strong>{failedCount}</strong>
          <p className="subtle">Конфигурации, которым нужно внимание администратора.</p>
        </article>
      </div>

      <div className="toolbar">
        <div>
          <h2>Задачи</h2>
          <p className="subtle">Управляйте задачами `db_backupper` и деплоем по namespace.</p>
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

      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>Название</th>
              <th>Namespace</th>
              <th>Включена</th>
              <th>Задеплоена</th>
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
                  <Link className="table-link" to={`/tasks/${task.id}`}>
                    {task.name}
                  </Link>
                </td>
                <td>{task.namespace}</td>
                <td>
                  <span className={task.enabled ? "status-badge success" : "status-badge"}>{formatBoolean(task.enabled)}</span>
                </td>
                <td>
                  <span className={task.deployed ? "status-badge success" : "status-badge"}>{formatBoolean(task.deployed)}</span>
                </td>
                <td>{task.schedule}</td>
                <td>
                  <span className={task.lastApplyStatus === "failed" ? "status-badge danger" : "status-badge"}>
                    {formatApplyStatus(task.lastApplyStatus)}
                  </span>
                </td>
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
                <td colSpan={8} className="empty-state">
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
