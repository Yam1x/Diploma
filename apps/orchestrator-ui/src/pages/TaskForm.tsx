import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ServiceDiscoveryResponse, ServiceType, TaskDetail, TaskPayload, api } from "../api/client";
import { ConfiguredSecrets, DiscoveryOption, TaskFormFields } from "../components/TaskFormFields";
import { getTaskTypeByRouteType, getTaskTypeByServiceType } from "../config/taskTypes";

const DEFAULT_SCHEDULE = "0 0 * * *";

function buildEmptyPayload(serviceType: ServiceType): TaskPayload {
  if (serviceType === "db_backupper") {
    return {
      serviceType,
      name: "",
      namespace: "",
      enabled: false,
      schedule: DEFAULT_SCHEDULE,
      triggerMode: "scheduled",
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

  if (serviceType === "s3_backupper") {
    return {
      serviceType,
      name: "",
      namespace: "",
      enabled: false,
      schedule: DEFAULT_SCHEDULE,
      triggerMode: "scheduled",
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

  return {
    serviceType,
    name: "",
    namespace: "",
    enabled: false,
    schedule: DEFAULT_SCHEDULE,
    triggerMode: "scheduled",
    envRepository: "",
    pathToHelmfile: "",
  };
}

function buildPayloadFromDetail(detail: TaskDetail): TaskPayload {
  if (detail.serviceType === "db_backupper") {
    return {
      serviceType: detail.serviceType,
      name: detail.name,
      namespace: detail.namespace,
      enabled: detail.enabled,
      schedule: detail.schedule ?? DEFAULT_SCHEDULE,
      triggerMode: "scheduled",
      dbBackupsFilenamePrefix: detail.dbBackupsFilenamePrefix,
      databaseHost: detail.databaseHost,
      databaseName: detail.databaseName,
      databaseUsername: detail.databaseUsername,
      databasePassword: "",
      destinationAwsEndpoint: detail.destinationAwsEndpoint,
      destinationAwsBucketName: detail.destinationAwsBucketName,
      destinationAwsAccessKeyId: detail.destinationAwsAccessKeyId,
      destinationAwsSecretAccessKey: "",
    };
  }

  if (detail.serviceType === "s3_backupper") {
    return {
      serviceType: detail.serviceType,
      name: detail.name,
      namespace: detail.namespace,
      enabled: detail.enabled,
      schedule: detail.schedule ?? DEFAULT_SCHEDULE,
      triggerMode: "scheduled",
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

  return {
    serviceType: detail.serviceType,
    name: detail.name,
    namespace: detail.namespace,
    enabled: detail.enabled,
    schedule: detail.schedule ?? DEFAULT_SCHEDULE,
    triggerMode: "scheduled",
    envRepository: detail.envRepository,
    pathToHelmfile: detail.pathToHelmfile,
  };
}

function buildConfiguredSecrets(detail: TaskDetail): ConfiguredSecrets {
  if (detail.serviceType === "db_backupper") {
    return {
      databasePassword: detail.hasDatabasePassword,
      destinationAwsSecretAccessKey: detail.hasDestinationAwsSecretAccessKey,
    };
  }

  if (detail.serviceType === "s3_backupper") {
    return {
      sourceS3AwsSecretAccessKey: detail.hasSourceS3AwsSecretAccessKey,
      destinationS3AwsSecretAccessKey: detail.hasDestinationS3AwsSecretAccessKey,
    };
  }

  return {};
}

function buildDbHostOptions(discovery: ServiceDiscoveryResponse): DiscoveryOption[] {
  return discovery.services.map((service) => ({
    label: `${service.name} -> ${service.host}`,
    value: service.host,
  }));
}

function buildS3EndpointOptions(discovery: ServiceDiscoveryResponse): DiscoveryOption[] {
  return discovery.services.flatMap((service) => service.endpoints);
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
  const [serviceDiscovery, setServiceDiscovery] = useState<ServiceDiscoveryResponse>({ services: [] });
  const [serviceDiscoveryLoading, setServiceDiscoveryLoading] = useState(false);
  const [serviceDiscoveryError, setServiceDiscoveryError] = useState<string | null>(null);

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

  useEffect(() => {
    if (!value?.namespace) {
      setServiceDiscovery({ services: [] });
      setServiceDiscoveryError(null);
      setServiceDiscoveryLoading(false);
      return;
    }

    let cancelled = false;
    setServiceDiscoveryLoading(true);

    void api
      .listServiceDiscovery(value.namespace)
      .then((response) => {
        if (cancelled) {
          return;
        }
        setServiceDiscovery(response);
        setServiceDiscoveryError(null);
      })
      .catch((err) => {
        if (cancelled) {
          return;
        }
        setServiceDiscovery({ services: [] });
        setServiceDiscoveryError(err instanceof Error ? err.message : "Не удалось загрузить service discovery");
      })
      .finally(() => {
        if (!cancelled) {
          setServiceDiscoveryLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [value?.namespace]);

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
        } else if (value.serviceType === "s3_backupper") {
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
  const dbHostOptions = useMemo(() => buildDbHostOptions(serviceDiscovery), [serviceDiscovery]);
  const s3EndpointOptions = useMemo(() => buildS3EndpointOptions(serviceDiscovery), [serviceDiscovery]);

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
            dbHostOptions={dbHostOptions}
            s3EndpointOptions={s3EndpointOptions}
            serviceDiscoveryLoading={serviceDiscoveryLoading}
            serviceDiscoveryError={serviceDiscoveryError}
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
