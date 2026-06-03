import { ChangeEvent, useEffect, useState } from "react";

import { TaskPayload } from "../api/client";
import { buildSchedule, parseSchedule, ScheduleDraft, ScheduleMode } from "../utils/schedule";

export type ConfiguredSecrets = {
  databasePassword?: boolean;
  destinationAwsSecretAccessKey?: boolean;
  sourceS3AwsSecretAccessKey?: boolean;
  destinationS3AwsSecretAccessKey?: boolean;
  sourceAwsSecretAccessKey?: boolean;
  targetDatabasePassword?: boolean;
  targetS3AwsSecretAccessKey?: boolean;
};

export type DiscoveryOption = {
  label: string;
  value: string;
};

type Props = {
  value: TaskPayload;
  onChange: (next: TaskPayload) => void;
  namespaceOptions: string[];
  configuredSecrets?: ConfiguredSecrets;
  dbHostOptions?: DiscoveryOption[];
  s3EndpointOptions?: DiscoveryOption[];
  serviceDiscoveryLoading?: boolean;
  serviceDiscoveryError?: string | null;
  onCreateNamespace?: () => void;
};

const scheduleModeOptions: Array<{ value: ScheduleMode; label: string }> = [
  { value: "hourly", label: "Каждый час" },
  { value: "daily", label: "Каждый день" },
  { value: "weekly", label: "Каждую неделю" },
  { value: "monthly", label: "Каждый месяц" },
  { value: "custom", label: "Свой cron" },
];

const weekdayOptions = [
  { value: "1", label: "Понедельник" },
  { value: "2", label: "Вторник" },
  { value: "3", label: "Среда" },
  { value: "4", label: "Четверг" },
  { value: "5", label: "Пятница" },
  { value: "6", label: "Суббота" },
  { value: "0", label: "Воскресенье" },
];

const DEFAULT_SCHEDULE = "0 0 * * *";

function getNormalizedSchedule(draft: ScheduleDraft): string {
  return draft.mode === "custom" ? draft.custom.trim() : buildSchedule(draft);
}

function isManualRecoveryTask(value: TaskPayload) {
  return value.serviceType === "db_restorer" || value.serviceType === "s3_restorer" || value.serviceType === "env_restorer";
}

function DiscoverySelect({
  ariaLabel,
  placeholder,
  options,
  disabled,
  onSelect,
}: {
  ariaLabel: string;
  placeholder: string;
  options: DiscoveryOption[];
  disabled: boolean;
  onSelect: (value: string) => void;
}) {
  return (
    <select
      aria-label={ariaLabel}
      value=""
      disabled={disabled}
      onChange={(event) => {
        if (!event.target.value) {
          return;
        }
        onSelect(event.target.value);
      }}
    >
      <option value="">{placeholder}</option>
      {options.map((option) => (
        <option key={`${option.value}:${option.label}`} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}

export function TaskFormFields({
  value,
  onChange,
  namespaceOptions,
  configuredSecrets,
  dbHostOptions = [],
  s3EndpointOptions = [],
  serviceDiscoveryLoading = false,
  serviceDiscoveryError,
  onCreateNamespace,
}: Props) {
  const [scheduleDraft, setScheduleDraft] = useState<ScheduleDraft>(() => parseSchedule(value.schedule ?? DEFAULT_SCHEDULE));

  useEffect(() => {
    setScheduleDraft((current) => {
      const nextSchedule = (value.schedule ?? "").trim();
      if (!nextSchedule) {
        return current;
      }

      const currentSchedule = getNormalizedSchedule(current);
      if (currentSchedule === nextSchedule) {
        return current;
      }

      return parseSchedule(nextSchedule);
    });
  }, [value.schedule]);

  const updateValue = (patch: Record<string, string | null>) => {
    onChange({ ...value, ...patch } as TaskPayload);
  };

  const update = (key: string) => (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    updateValue({ [key]: event.target.value });
  };

  const applyScheduleDraft = (nextDraft: ScheduleDraft) => {
    setScheduleDraft(nextDraft);

    const nextSchedule = getNormalizedSchedule(nextDraft);
    if (nextSchedule !== value.schedule) {
      onChange({ ...value, schedule: nextSchedule } as TaskPayload);
    }
  };

  const updateScheduleDraft = (patch: Partial<ScheduleDraft>) => {
    applyScheduleDraft({ ...scheduleDraft, ...patch });
  };

  const handleScheduleModeChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const nextMode = event.target.value as ScheduleMode;
    applyScheduleDraft({
      ...scheduleDraft,
      mode: nextMode,
      custom: scheduleDraft.custom || value.schedule || DEFAULT_SCHEDULE,
    });
  };

  const cronPreview = getNormalizedSchedule(scheduleDraft) || "Не задано";
  const serviceDiscoveryPlaceholder = !value.namespace
    ? "Сначала выберите namespace"
    : serviceDiscoveryLoading
      ? "Загружаем сервисы..."
      : "Подставить из Service Discovery";
  const serviceDiscoveryEnabled = Boolean(value.namespace) && !serviceDiscoveryLoading;
  const usesSchedule = !isManualRecoveryTask(value);

  function renderSchedule() {
    if (!usesSchedule) {
      return null;
    }

    return (
      <div className="schedule-field">
        <div>
          <span>Расписание</span>
          <small className="field-help">Выберите режим запуска, а интерфейс соберёт cron-выражение автоматически.</small>
        </div>
        <div className="schedule-grid">
          <label>
            <span>Режим</span>
            <select value={scheduleDraft.mode} onChange={handleScheduleModeChange}>
              {scheduleModeOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          {scheduleDraft.mode === "hourly" ? (
            <label>
              <span>Минута часа</span>
              <input
                type="number"
                min="0"
                max="59"
                value={scheduleDraft.minute}
                onChange={(event) => updateScheduleDraft({ minute: event.target.value })}
              />
            </label>
          ) : null}

          {scheduleDraft.mode === "daily" || scheduleDraft.mode === "weekly" || scheduleDraft.mode === "monthly" ? (
            <label>
              <span>Время</span>
              <input type="time" value={scheduleDraft.time} onChange={(event) => updateScheduleDraft({ time: event.target.value })} />
            </label>
          ) : null}

          {scheduleDraft.mode === "weekly" ? (
            <label>
              <span>День недели</span>
              <select value={scheduleDraft.weekday} onChange={(event) => updateScheduleDraft({ weekday: event.target.value })}>
                {weekdayOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          {scheduleDraft.mode === "monthly" ? (
            <label>
              <span>День месяца</span>
              <input
                type="number"
                min="1"
                max="31"
                value={scheduleDraft.monthDay}
                onChange={(event) => updateScheduleDraft({ monthDay: event.target.value })}
              />
            </label>
          ) : null}

          {scheduleDraft.mode === "custom" ? (
            <label className="schedule-grid-full">
              <span>Cron-выражение</span>
              <input
                value={scheduleDraft.custom}
                onChange={(event) => applyScheduleDraft({ ...scheduleDraft, custom: event.target.value })}
                placeholder="0 * * * *"
                required
              />
            </label>
          ) : null}
        </div>
        <div className="schedule-preview">
          <span>Итоговый cron</span>
          <code>{cronPreview}</code>
        </div>
      </div>
    );
  }

  function renderManualAlert() {
    if (usesSchedule) {
      return null;
    }
    return <div className="alert">Эта recovery-задача не использует расписание. Деплой только подготавливает доступ, а восстановление запускается вручную.</div>;
  }

  function renderDbBackupperFields() {
    if (value.serviceType !== "db_backupper") {
      return null;
    }

    return (
      <>
        <label>
          <span>Префикс имени файла</span>
          <small className="field-help">Префикс, который будет добавляться к имени каждого созданного дампа.</small>
          <input value={value.dbBackupsFilenamePrefix} onChange={update("dbBackupsFilenamePrefix")} required />
        </label>
        <label>
          <span>Хост базы данных</span>
          <small className="field-help">Адрес PostgreSQL, к которому будет подключаться backup job.</small>
          <div className="discovery-field">
            <input value={value.databaseHost} onChange={update("databaseHost")} required />
            <DiscoverySelect
              ariaLabel="Service Discovery: хост базы данных"
              placeholder={serviceDiscoveryPlaceholder}
              options={dbHostOptions}
              disabled={!serviceDiscoveryEnabled || dbHostOptions.length === 0}
              onSelect={(nextValue) => updateValue({ databaseHost: nextValue })}
            />
          </div>
        </label>
        <label>
          <span>Имя базы данных</span>
          <small className="field-help">База данных, из которой нужно снимать резервные копии.</small>
          <input value={value.databaseName} onChange={update("databaseName")} required />
        </label>
        <label>
          <span>Пользователь базы данных</span>
          <small className="field-help">Пользователь, от имени которого backup job будет подключаться к PostgreSQL.</small>
          <input value={value.databaseUsername} onChange={update("databaseUsername")} required />
        </label>
        <label>
          <span>Пароль базы данных {configuredSecrets?.databasePassword ? "(настроен)" : ""}</span>
          <small className="field-help">Оставьте поле пустым, чтобы не менять уже сохранённое значение.</small>
          <input type="password" value={value.databasePassword ?? ""} onChange={update("databasePassword")} />
        </label>
        <label>
          <span>S3 endpoint</span>
          <small className="field-help">Адрес S3-совместимого хранилища, в которое будет отправляться дамп.</small>
          <div className="discovery-field">
            <input value={value.destinationAwsEndpoint} onChange={update("destinationAwsEndpoint")} required />
            <DiscoverySelect
              ariaLabel="Service Discovery: S3 endpoint для db backupper"
              placeholder={serviceDiscoveryPlaceholder}
              options={s3EndpointOptions}
              disabled={!serviceDiscoveryEnabled || s3EndpointOptions.length === 0}
              onSelect={(nextValue) => updateValue({ destinationAwsEndpoint: nextValue })}
            />
          </div>
        </label>
        <label>
          <span>S3 bucket</span>
          <small className="field-help">Bucket, в котором будут храниться резервные копии базы данных.</small>
          <input value={value.destinationAwsBucketName} onChange={update("destinationAwsBucketName")} required />
        </label>
        <label>
          <span>S3 access key</span>
          <small className="field-help">Публичный ключ доступа к S3.</small>
          <input value={value.destinationAwsAccessKeyId} onChange={update("destinationAwsAccessKeyId")} required />
        </label>
        <label>
          <span>S3 secret key {configuredSecrets?.destinationAwsSecretAccessKey ? "(настроен)" : ""}</span>
          <small className="field-help">Оставьте поле пустым, чтобы сохранить текущее значение.</small>
          <input type="password" value={value.destinationAwsSecretAccessKey ?? ""} onChange={update("destinationAwsSecretAccessKey")} />
        </label>
      </>
    );
  }

  function renderS3BackupperFields() {
    if (value.serviceType !== "s3_backupper") {
      return null;
    }

    return (
      <>
        <label>
          <span>Префикс имени архива</span>
          <small className="field-help">Префикс, который будет добавляться к имени каждого архива с данными из исходного bucket.</small>
          <input value={value.s3BackupsFilenamePrefix} onChange={update("s3BackupsFilenamePrefix")} required />
        </label>
        <label>
          <span>Source S3 endpoint</span>
          <small className="field-help">Адрес исходного S3-хранилища, из которого job будет читать файлы.</small>
          <div className="discovery-field">
            <input value={value.sourceS3AwsEndpoint} onChange={update("sourceS3AwsEndpoint")} required />
            <DiscoverySelect
              ariaLabel="Service Discovery: source S3 endpoint"
              placeholder={serviceDiscoveryPlaceholder}
              options={s3EndpointOptions}
              disabled={!serviceDiscoveryEnabled || s3EndpointOptions.length === 0}
              onSelect={(nextValue) => updateValue({ sourceS3AwsEndpoint: nextValue })}
            />
          </div>
        </label>
        <label>
          <span>Source S3 bucket</span>
          <small className="field-help">Имя bucket, содержимое которого нужно архивировать.</small>
          <input value={value.sourceS3AwsBucketName} onChange={update("sourceS3AwsBucketName")} required />
        </label>
        <label>
          <span>Source S3 subfolder</span>
          <small className="field-help">Необязательный подкаталог внутри bucket. Оставьте пустым, чтобы архивировать весь bucket.</small>
          <input value={value.sourceS3AwsBucketSubfolderName} onChange={update("sourceS3AwsBucketSubfolderName")} />
        </label>
        <label>
          <span>Source S3 access key</span>
          <small className="field-help">Публичный ключ доступа к исходному S3.</small>
          <input value={value.sourceS3AwsAccessKeyId} onChange={update("sourceS3AwsAccessKeyId")} required />
        </label>
        <label>
          <span>Source S3 secret key {configuredSecrets?.sourceS3AwsSecretAccessKey ? "(настроен)" : ""}</span>
          <small className="field-help">Оставьте поле пустым, чтобы сохранить текущее значение.</small>
          <input type="password" value={value.sourceS3AwsSecretAccessKey ?? ""} onChange={update("sourceS3AwsSecretAccessKey")} />
        </label>
        <label>
          <span>Destination S3 endpoint</span>
          <small className="field-help">Адрес целевого S3-хранилища, куда будет загружен архив.</small>
          <input value={value.destinationS3AwsEndpoint} onChange={update("destinationS3AwsEndpoint")} required />
        </label>
        <label>
          <span>Destination S3 bucket</span>
          <small className="field-help">Bucket, в который будет загружен сформированный архив.</small>
          <input value={value.destinationS3AwsBucketName} onChange={update("destinationS3AwsBucketName")} required />
        </label>
        <label>
          <span>Destination S3 access key</span>
          <small className="field-help">Публичный ключ доступа к целевому S3.</small>
          <input value={value.destinationS3AwsAccessKeyId} onChange={update("destinationS3AwsAccessKeyId")} required />
        </label>
        <label>
          <span>Destination S3 secret key {configuredSecrets?.destinationS3AwsSecretAccessKey ? "(настроен)" : ""}</span>
          <small className="field-help">Оставьте поле пустым, чтобы сохранить текущее значение.</small>
          <input type="password" value={value.destinationS3AwsSecretAccessKey ?? ""} onChange={update("destinationS3AwsSecretAccessKey")} />
        </label>
      </>
    );
  }

  function renderEnvBackupOrRestoreFields() {
    if (value.serviceType !== "env_backupper" && value.serviceType !== "env_restorer") {
      return null;
    }

    const endpointLabel = value.serviceType === "env_backupper" ? "S3 endpoint" : "Source S3 endpoint";
    const bucketLabel = value.serviceType === "env_backupper" ? "S3 bucket" : "Source S3 bucket";
    const accessKeyLabel = value.serviceType === "env_backupper" ? "S3 access key" : "Source S3 access key";
    const secretLabel = value.serviceType === "env_backupper" ? "S3 secret key" : "Source S3 secret key";

    return (
      <>
        <label>
          <span>Префикс имени архива</span>
          <small className="field-help">Префикс, который будет добавляться к имени каждого snapshot-архива namespace.</small>
          <input value={value.envBackupsFilenamePrefix} onChange={update("envBackupsFilenamePrefix")} required />
        </label>
        <label>
          <span>{endpointLabel}</span>
          <small className="field-help">Адрес S3/MinIO, где хранится или будет храниться архив состояния namespace.</small>
          <div className="discovery-field">
            <input value={value.destinationAwsEndpoint} onChange={update("destinationAwsEndpoint")} required />
            <DiscoverySelect
              ariaLabel={value.serviceType === "env_backupper" ? "Service Discovery: S3 endpoint для env backupper" : "Service Discovery: source S3 endpoint for env restorer"}
              placeholder={serviceDiscoveryPlaceholder}
              options={s3EndpointOptions}
              disabled={!serviceDiscoveryEnabled || s3EndpointOptions.length === 0}
              onSelect={(nextValue) => updateValue({ destinationAwsEndpoint: nextValue })}
            />
          </div>
        </label>
        <label>
          <span>{bucketLabel}</span>
          <small className="field-help">Bucket, в котором будут храниться snapshot-архивы выбранного namespace.</small>
          <input value={value.destinationAwsBucketName} onChange={update("destinationAwsBucketName")} required />
        </label>
        <label>
          <span>{accessKeyLabel}</span>
          <small className="field-help">Публичный ключ доступа к S3/MinIO.</small>
          <input value={value.destinationAwsAccessKeyId} onChange={update("destinationAwsAccessKeyId")} required />
        </label>
        <label>
          <span>
            {secretLabel} {configuredSecrets?.destinationAwsSecretAccessKey ? "(настроен)" : ""}
          </span>
          <small className="field-help">Оставьте поле пустым, чтобы не менять сохранённое значение.</small>
          <input type="password" value={value.destinationAwsSecretAccessKey ?? ""} onChange={update("destinationAwsSecretAccessKey")} />
        </label>
      </>
    );
  }

  function renderDbRestorerFields() {
    if (value.serviceType !== "db_restorer") {
      return null;
    }

    return (
      <>
        <label>
          <span>Префикс имени файла</span>
          <small className="field-help">Префикс, по которому `db_restorer` ищет резервные дампы в исходном bucket.</small>
          <input value={value.dbBackupsFilenamePrefix} onChange={update("dbBackupsFilenamePrefix")} required />
        </label>
        <label>
          <span>Source S3 endpoint</span>
          <small className="field-help">Адрес S3/MinIO, где лежат дампы для восстановления.</small>
          <div className="discovery-field">
            <input value={value.sourceAwsEndpoint} onChange={update("sourceAwsEndpoint")} required />
            <DiscoverySelect
              ariaLabel="Service Discovery: source S3 endpoint for db restorer"
              placeholder={serviceDiscoveryPlaceholder}
              options={s3EndpointOptions}
              disabled={!serviceDiscoveryEnabled || s3EndpointOptions.length === 0}
              onSelect={(nextValue) => updateValue({ sourceAwsEndpoint: nextValue })}
            />
          </div>
        </label>
        <label>
          <span>Source S3 bucket</span>
          <small className="field-help">Bucket, из которого `db_restorer` будет брать последний дамп.</small>
          <input value={value.sourceAwsBucketName} onChange={update("sourceAwsBucketName")} required />
        </label>
        <label>
          <span>Source S3 access key</span>
          <small className="field-help">Публичный ключ доступа к исходному S3.</small>
          <input value={value.sourceAwsAccessKeyId} onChange={update("sourceAwsAccessKeyId")} required />
        </label>
        <label>
          <span>Source S3 secret key {configuredSecrets?.sourceAwsSecretAccessKey ? "(настроен)" : ""}</span>
          <small className="field-help">Оставьте поле пустым, чтобы сохранить текущее значение.</small>
          <input type="password" value={value.sourceAwsSecretAccessKey ?? ""} onChange={update("sourceAwsSecretAccessKey")} />
        </label>
        <label>
          <span>Хост целевой базы данных</span>
          <small className="field-help">Адрес PostgreSQL, в который будет восстановлен последний дамп.</small>
          <div className="discovery-field">
            <input value={value.targetDatabaseHost} onChange={update("targetDatabaseHost")} required />
            <DiscoverySelect
              ariaLabel="Service Discovery: target database host"
              placeholder={serviceDiscoveryPlaceholder}
              options={dbHostOptions}
              disabled={!serviceDiscoveryEnabled || dbHostOptions.length === 0}
              onSelect={(nextValue) => updateValue({ targetDatabaseHost: nextValue })}
            />
          </div>
        </label>
        <label>
          <span>Имя целевой базы данных</span>
          <small className="field-help">База данных, в которую будет восстановлен дамп.</small>
          <input value={value.targetDatabaseName} onChange={update("targetDatabaseName")} required />
        </label>
        <label>
          <span>Пользователь целевой базы данных</span>
          <small className="field-help">Пользователь, от имени которого restore job будет подключаться к PostgreSQL.</small>
          <input value={value.targetDatabaseUsername} onChange={update("targetDatabaseUsername")} required />
        </label>
        <label>
          <span>Пароль целевой базы данных {configuredSecrets?.targetDatabasePassword ? "(настроен)" : ""}</span>
          <small className="field-help">Оставьте поле пустым, чтобы сохранить текущее значение.</small>
          <input type="password" value={value.targetDatabasePassword ?? ""} onChange={update("targetDatabasePassword")} />
        </label>
      </>
    );
  }

  function renderS3RestorerFields() {
    if (value.serviceType !== "s3_restorer") {
      return null;
    }

    return (
      <>
        <label>
          <span>Префикс имени архива</span>
          <small className="field-help">Префикс, по которому `s3_restorer` ищет архивы в исходном bucket.</small>
          <input value={value.s3BackupsFilenamePrefix} onChange={update("s3BackupsFilenamePrefix")} required />
        </label>
        <label>
          <span>Source S3 endpoint</span>
          <small className="field-help">Адрес S3/MinIO, где лежат архивы для восстановления.</small>
          <div className="discovery-field">
            <input value={value.sourceS3AwsEndpoint} onChange={update("sourceS3AwsEndpoint")} required />
            <DiscoverySelect
              ariaLabel="Service Discovery: source S3 endpoint for s3 restorer"
              placeholder={serviceDiscoveryPlaceholder}
              options={s3EndpointOptions}
              disabled={!serviceDiscoveryEnabled || s3EndpointOptions.length === 0}
              onSelect={(nextValue) => updateValue({ sourceS3AwsEndpoint: nextValue })}
            />
          </div>
        </label>
        <label>
          <span>Source S3 bucket</span>
          <small className="field-help">Bucket, из которого `s3_restorer` будет брать последний архив.</small>
          <input value={value.sourceS3AwsBucketName} onChange={update("sourceS3AwsBucketName")} required />
        </label>
        <label>
          <span>Source S3 access key</span>
          <small className="field-help">Публичный ключ доступа к исходному S3.</small>
          <input value={value.sourceS3AwsAccessKeyId} onChange={update("sourceS3AwsAccessKeyId")} required />
        </label>
        <label>
          <span>Source S3 secret key {configuredSecrets?.sourceS3AwsSecretAccessKey ? "(настроен)" : ""}</span>
          <small className="field-help">Оставьте поле пустым, чтобы сохранить текущее значение.</small>
          <input type="password" value={value.sourceS3AwsSecretAccessKey ?? ""} onChange={update("sourceS3AwsSecretAccessKey")} />
        </label>
        <label>
          <span>Target S3 endpoint</span>
          <small className="field-help">Адрес целевого S3-хранилища, в которое будет восстановлен архив.</small>
          <div className="discovery-field">
            <input value={value.targetS3AwsEndpoint} onChange={update("targetS3AwsEndpoint")} required />
            <DiscoverySelect
              ariaLabel="Service Discovery: target S3 endpoint for s3 restorer"
              placeholder={serviceDiscoveryPlaceholder}
              options={s3EndpointOptions}
              disabled={!serviceDiscoveryEnabled || s3EndpointOptions.length === 0}
              onSelect={(nextValue) => updateValue({ targetS3AwsEndpoint: nextValue })}
            />
          </div>
        </label>
        <label>
          <span>Target S3 bucket</span>
          <small className="field-help">Bucket, в который будет восстановлено содержимое архива.</small>
          <input value={value.targetS3AwsBucketName} onChange={update("targetS3AwsBucketName")} required />
        </label>
        <label>
          <span>Target S3 subfolder</span>
          <small className="field-help">Необязательный подкаталог внутри целевого bucket.</small>
          <input value={value.targetS3AwsBucketSubfolderName} onChange={update("targetS3AwsBucketSubfolderName")} />
        </label>
        <label>
          <span>Target S3 access key</span>
          <small className="field-help">Публичный ключ доступа к целевому S3.</small>
          <input value={value.targetS3AwsAccessKeyId} onChange={update("targetS3AwsAccessKeyId")} required />
        </label>
        <label>
          <span>Target S3 secret key {configuredSecrets?.targetS3AwsSecretAccessKey ? "(настроен)" : ""}</span>
          <small className="field-help">Оставьте поле пустым, чтобы сохранить текущее значение.</small>
          <input type="password" value={value.targetS3AwsSecretAccessKey ?? ""} onChange={update("targetS3AwsSecretAccessKey")} />
        </label>
      </>
    );
  }

  function renderEnvSynchronizerFields() {
    if (value.serviceType !== "env_synchronizer") {
      return null;
    }

    return (
      <>
        <label>
          <span>Репозиторий окружения</span>
          <small className="field-help">GitHub-репозиторий в формате `owner/repo`, который будет клонировать synchronizer.</small>
          <input value={value.envRepository} onChange={update("envRepository")} placeholder="owner/repo" required />
        </label>
        <label>
          <span>Путь к Helmfile</span>
          <small className="field-help">Путь до Helmfile внутри репозитория окружения, который нужно применять по расписанию.</small>
          <input value={value.pathToHelmfile} onChange={update("pathToHelmfile")} placeholder="deploy/helmfile.yaml.gotmpl" required />
        </label>
      </>
    );
  }

  return (
    <div className="card form-grid">
      <label>
        <span>Название</span>
        <small className="field-help">Понятное имя задачи, под которым она будет отображаться в панели управления.</small>
        <input value={value.name} onChange={update("name")} required />
      </label>

      {value.serviceType === "db_backupper" ? (
        <label>
          <span>Режим запуска</span>
          <small className="field-help">Переключает DB backup между cron-запуском и событийным режимом.</small>
          <select
            value={value.triggerMode}
            onChange={(event) => onChange({ ...value, triggerMode: event.target.value as TaskPayload["triggerMode"] })}
          >
            <option value="scheduled">По расписанию</option>
          </select>
        </label>
      ) : null}

      <label>
        <span>Namespace</span>
        <small className="field-help">Namespace Kubernetes, в который будет задеплоен сервис резервного копирования или восстановления.</small>
        <div className="namespace-field">
          <select value={value.namespace} onChange={update("namespace")}>
            <option value="">Выберите namespace</option>
            {namespaceOptions.map((namespace) => (
              <option key={namespace} value={namespace}>
                {namespace}
              </option>
            ))}
          </select>
          <button type="button" className="button ghost" onClick={onCreateNamespace}>
            Создать namespace
          </button>
        </div>
        {serviceDiscoveryError ? <small className="field-help discovery-note">Service Discovery: {serviceDiscoveryError}</small> : null}
      </label>

      {renderSchedule()}
      {renderManualAlert()}


      {renderDbBackupperFields()}
      {renderS3BackupperFields()}
      {renderDbRestorerFields()}
      {renderS3RestorerFields()}
      {renderEnvBackupOrRestoreFields()}
      {renderEnvSynchronizerFields()}

      <label className="toggle">
        <input type="checkbox" checked={value.enabled} onChange={(event) => onChange({ ...value, enabled: event.target.checked } as TaskPayload)} />
        <span>Включить деплой после сохранения</span>
      </label>
    </div>
  );
}
