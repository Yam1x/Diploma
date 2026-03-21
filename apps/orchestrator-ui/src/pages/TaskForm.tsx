import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { DbTaskDetail, ServiceType, TaskDetail, TaskPayload, api } from "../api/client";
import { ConfiguredSecrets, TaskFormFields } from "../components/TaskFormFields";
import { getTaskTypeByRouteType, getTaskTypeByServiceType } from "../config/taskTypes";

function buildEmptyPayload(serviceType: ServiceType): TaskPayload {
  if (serviceType === "db_backupper") {
    return {
      serviceType,
      name: "",
      namespace: "",
      enabled: false,
      schedule: "0 0 * * *",
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
  }

  return {
    serviceType,
    name: "",
    namespace: "",
    enabled: false,
    schedule: "0 0 * * *",
    s3BackupsFilenamePrefix: "",
    sourceS3AwsEndpoint: "",
    sourceS3AwsAccessKeyId: "",
    sourceS3AwsBucketName: "",
    sourceS3AwsBucketSubfolderName: "",
    sourceS3AwsSecretAccessKey: "",
    destinationS3AwsEndpoint: "",
    destinationS3AwsAccessKeyId: "",
    destinationS3AwsBucketName: "",
    destinationS3AwsSecretAccessKey: "",
  };
}

function buildPayloadFromDetail(detail: TaskDetail): TaskPayload {
  if (detail.serviceType === "db_backupper") {
    const dbDetail = detail as DbTaskDetail;
    return {
      serviceType: dbDetail.serviceType,
      name: dbDetail.name,
      namespace: dbDetail.namespace,
      enabled: dbDetail.enabled,
      schedule: dbDetail.schedule,
      dbBackupsFilenamePrefix: dbDetail.dbBackupsFilenamePrefix,
      databaseHost: dbDetail.databaseHost,
      databaseName: dbDetail.databaseName,
      databaseUsername: dbDetail.databaseUsername,
      databasePassword: "",
      destinationAwsEndpoint: dbDetail.destinationAwsEndpoint,
      destinationAwsBucketName: dbDetail.destinationAwsBucketName,
      destinationAwsAccessKeyId: dbDetail.destinationAwsAccessKeyId,
      destinationAwsSecretAccessKey: "",
    };
  }

  return {
    serviceType: detail.serviceType,
    name: detail.name,
    namespace: detail.namespace,
    enabled: detail.enabled,
    schedule: detail.schedule,
    s3BackupsFilenamePrefix: detail.s3BackupsFilenamePrefix,
    sourceS3AwsEndpoint: detail.sourceS3AwsEndpoint,
    sourceS3AwsAccessKeyId: detail.sourceS3AwsAccessKeyId,
    sourceS3AwsBucketName: detail.sourceS3AwsBucketName,
    sourceS3AwsBucketSubfolderName: detail.sourceS3AwsBucketSubfolderName,
    sourceS3AwsSecretAccessKey: "",
    destinationS3AwsEndpoint: detail.destinationS3AwsEndpoint,
    destinationS3AwsAccessKeyId: detail.destinationS3AwsAccessKeyId,
    destinationS3AwsBucketName: detail.destinationS3AwsBucketName,
    destinationS3AwsSecretAccessKey: "",
  };
}

function buildConfiguredSecrets(detail: TaskDetail): ConfiguredSecrets {
  if (detail.serviceType === "db_backupper") {
    return {
      databasePassword: detail.hasDatabasePassword,
      destinationAwsSecretAccessKey: detail.hasDestinationAwsSecretAccessKey,
    };
  }

  return {
    sourceS3AwsSecretAccessKey: detail.hasSourceS3AwsSecretAccessKey,
    destinationS3AwsSecretAccessKey: detail.hasDestinationS3AwsSecretAccessKey,
  };
}

export function TaskFormPage() {
  const navigate = useNavigate();
  const { taskId, taskType } = useParams();
  const isEditMode = Boolean(taskId);
  const selectedTaskType = getTaskTypeByRouteType(taskType);
  const [value, setValue] = useState<TaskPayload | null>(null);
  const [namespaces, setNamespaces] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [configuredSecrets, setConfiguredSecrets] = useState<ConfiguredSecrets>({});

  useEffect(() => {
    async function load() {
      if (!isEditMode && !selectedTaskType) {
        setError("Выбранный тип задачи пока не поддерживается.");
        setValue(null);
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
          setValue(buildPayloadFromDetail(detail));
          setConfiguredSecrets(buildConfiguredSecrets(detail));
          return;
        }

        if (selectedTaskType) {
          setValue(buildEmptyPayload(selectedTaskType.serviceType));
          setConfiguredSecrets({});
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
      setValue((current) => (current ? { ...current, namespace: response.name } : current));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось создать namespace");
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!value) {
      return;
    }

    try {
      if (taskId) {
        const payload = { ...value } as Record<string, unknown>;
        if (value.serviceType === "db_backupper") {
          if (!value.databasePassword) {
            delete payload.databasePassword;
          }
          if (!value.destinationAwsSecretAccessKey) {
            delete payload.destinationAwsSecretAccessKey;
          }
        } else {
          if (!value.sourceS3AwsSecretAccessKey) {
            delete payload.sourceS3AwsSecretAccessKey;
          }
          if (!value.destinationS3AwsSecretAccessKey) {
            delete payload.destinationS3AwsSecretAccessKey;
          }
        }
        await api.updateTask(taskId, payload as TaskPayload);
        navigate(`/tasks/${taskId}`);
      } else {
        const task = await api.createTask(value);
        navigate(`/tasks/${task.id}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сохранить задачу");
    }
  }

  const activeTaskType = value ? getTaskTypeByServiceType(value.serviceType) : selectedTaskType;

  return (
    <section className="stack">
      <div className="toolbar">
        <div>
          <h2>{taskId ? "Редактирование задачи" : "Создание задачи"}</h2>
          <p className="subtle">
            {activeTaskType
              ? `Настройте желаемое состояние и параметры деплоя для сервиса «${activeTaskType.title}».`
              : "Настройте желаемое состояние и параметры деплоя задачи."}
          </p>
        </div>
        <Link className="button ghost" to={taskId ? `/tasks/${taskId}` : "/tasks/new"}>
          Отмена
        </Link>
      </div>
      {error ? <div className="alert">{error}</div> : null}
      {value ? (
        <form className="stack" onSubmit={(event) => void handleSubmit(event)}>
          <TaskFormFields
            value={value}
            onChange={setValue}
            namespaceOptions={namespaces}
            configuredSecrets={configuredSecrets}
            onCreateNamespace={() => void handleCreateNamespace()}
          />
          <div className="toolbar-actions">
            <button className="button primary" type="submit" disabled={!isEditMode && !selectedTaskType}>
              Сохранить задачу
            </button>
          </div>
        </form>
      ) : error ? null : (
        <p>Загрузка...</p>
      )}
    </section>
  );
}
