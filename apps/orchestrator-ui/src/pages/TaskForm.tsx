import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api, TaskPayload } from "../api/client";
import { TaskFormFields } from "../components/TaskFormFields";
import { getTaskTypeByRouteType } from "../config/taskTypes";

const emptyPayload: TaskPayload = {
  name: "",
  namespace: "",
  enabled: false,
  schedule: "",
  dbBackupsFilenamePrefix: "",
  databaseHost: "",
  databaseName: "",
  databaseUsername: "",
  databasePassword: "",
  destinationAwsEndpoint: "",
  destinationAwsBucketName: "",
  destinationAwsAccessKeyId: "",
  destinationAwsSecretAccessKey: "",
};

export function TaskFormPage() {
  const navigate = useNavigate();
  const { taskId, taskType } = useParams();
  const isEditMode = Boolean(taskId);
  const selectedTaskType = getTaskTypeByRouteType(taskType);
  const [value, setValue] = useState<TaskPayload>(emptyPayload);
  const [namespaces, setNamespaces] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [passwordConfigured, setPasswordConfigured] = useState(false);
  const [secretConfigured, setSecretConfigured] = useState(false);

  useEffect(() => {
    async function load() {
      if (!isEditMode && !selectedTaskType) {
        setError("Выбранный тип задачи пока не поддерживается.");
        return;
      }

      try {
        const [{ namespaces: namespaceList }, detail] = await Promise.all([
          api.listNamespaces(),
          taskId ? api.getTask(taskId) : Promise.resolve(null),
        ]);
        setNamespaces(namespaceList);
        setError(null);
        if (detail) {
          setValue({
            name: detail.name,
            namespace: detail.namespace,
            enabled: detail.enabled,
            schedule: detail.schedule,
            dbBackupsFilenamePrefix: detail.dbBackupsFilenamePrefix,
            databaseHost: detail.databaseHost,
            databaseName: detail.databaseName,
            databaseUsername: detail.databaseUsername,
            databasePassword: "",
            destinationAwsEndpoint: detail.destinationAwsEndpoint,
            destinationAwsBucketName: detail.destinationAwsBucketName,
            destinationAwsAccessKeyId: detail.destinationAwsAccessKeyId,
            destinationAwsSecretAccessKey: "",
          });
          setPasswordConfigured(detail.hasDatabasePassword);
          setSecretConfigured(detail.hasDestinationAwsSecretAccessKey);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Не удалось загрузить форму");
      }
    }

    void load();
  }, [isEditMode, selectedTaskType, taskId]);

  async function handleCreateNamespace() {
    const name = window.prompt("Введите имя namespace");
    const namespace = name?.trim();
    if (!namespace) {
      return;
    }
    try {
      const response = await api.createNamespace({ name: namespace });
      const namespaceList = await api.listNamespaces();
      setNamespaces(namespaceList.namespaces);
      setValue((current) => ({ ...current, namespace: response.name }));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось создать namespace");
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    try {
      if (taskId) {
        const payload: Partial<TaskPayload> = { ...value };
        if (!payload.databasePassword) {
          delete payload.databasePassword;
        }
        if (!payload.destinationAwsSecretAccessKey) {
          delete payload.destinationAwsSecretAccessKey;
        }
        await api.updateTask(taskId, payload);
        navigate(`/tasks/${taskId}`);
      } else {
        const task = await api.createTask(value);
        navigate(`/tasks/${task.id}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сохранить задачу");
    }
  }

  return (
    <section className="stack">
      <div className="toolbar">
        <div>
          <h2>{taskId ? "Редактирование задачи" : "Создание задачи"}</h2>
          <p className="subtle">
            {selectedTaskType
              ? `Настройте желаемое состояние и параметры деплоя для сервиса «${selectedTaskType.title}».`
              : "Настройте желаемое состояние и параметры деплоя задачи."}
          </p>
        </div>
        <Link className="button ghost" to={taskId ? `/tasks/${taskId}` : "/tasks/new"}>
          Отмена
        </Link>
      </div>
      {error ? <div className="alert">{error}</div> : null}
      <form className="stack" onSubmit={(event) => void handleSubmit(event)}>
        <TaskFormFields
          value={value}
          onChange={setValue}
          namespaceOptions={namespaces}
          passwordConfigured={passwordConfigured}
          secretConfigured={secretConfigured}
          onCreateNamespace={() => void handleCreateNamespace()}
        />
        <div className="toolbar-actions">
          <button className="button primary" type="submit" disabled={!isEditMode && !selectedTaskType}>
            Сохранить задачу
          </button>
        </div>
      </form>
    </section>
  );
}
