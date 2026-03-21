import { ChangeEvent, useEffect, useState } from "react";

import { DbTaskPayload, S3TaskPayload, TaskPayload } from "../api/client";
import { buildSchedule, parseSchedule, ScheduleDraft, ScheduleMode } from "../utils/schedule";

export type ConfiguredSecrets = {
  databasePassword?: boolean;
  destinationAwsSecretAccessKey?: boolean;
  sourceS3AwsSecretAccessKey?: boolean;
  destinationS3AwsSecretAccessKey?: boolean;
};

type Props = {
  value: TaskPayload;
  onChange: (next: TaskPayload) => void;
  namespaceOptions: string[];
  configuredSecrets?: ConfiguredSecrets;
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

function getNormalizedSchedule(draft: ScheduleDraft): string {
  return draft.mode === "custom" ? draft.custom.trim() : buildSchedule(draft);
}

export function TaskFormFields({ value, onChange, namespaceOptions, configuredSecrets, onCreateNamespace }: Props) {
  const [scheduleDraft, setScheduleDraft] = useState<ScheduleDraft>(() => parseSchedule(value.schedule));

  useEffect(() => {
    setScheduleDraft((current) => {
      const currentSchedule = getNormalizedSchedule(current);
      const nextSchedule = value.schedule.trim();

      if (currentSchedule === nextSchedule) {
        return current;
      }

      return parseSchedule(value.schedule);
    });
  }, [value.schedule]);

  const updateValue = (patch: Partial<DbTaskPayload> | Partial<S3TaskPayload>) => {
    onChange({ ...value, ...patch } as TaskPayload);
  };

  const update = (key: string) => (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    updateValue({ [key]: event.target.value } as Partial<DbTaskPayload> & Partial<S3TaskPayload>);
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
      custom: scheduleDraft.custom || value.schedule,
    });
  };

  const cronPreview = getNormalizedSchedule(scheduleDraft) || "Не задано";

  return (
    <div className="card form-grid">
      <label>
        <span>Название</span>
        <small className="field-help">Понятное имя задачи, под которым она будет отображаться в панели управления.</small>
        <input value={value.name} onChange={update("name")} required />
      </label>
      <label>
        <span>Namespace</span>
        <small className="field-help">Namespace Kubernetes, в который будет задеплоен сервис резервного копирования.</small>
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
      </label>
      <div className="schedule-field">
        <div>
          <span>Расписание</span>
          <small className="field-help">Выберите готовый режим запуска, а интерфейс сам соберет cron-выражение.</small>
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
                onChange={(event) => {
                  const nextCustom = event.target.value;
                  applyScheduleDraft({ ...scheduleDraft, custom: nextCustom });
                }}
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

      {value.serviceType === "db_backupper" ? (
        <>
          <label>
            <span>Префикс имени файла</span>
            <small className="field-help">Префикс, который будет добавляться к имени каждого созданного дампа.</small>
            <input value={value.dbBackupsFilenamePrefix} onChange={update("dbBackupsFilenamePrefix")} required />
          </label>
          <label>
            <span>Хост базы данных</span>
            <small className="field-help">Адрес PostgreSQL, к которому будет подключаться backup job.</small>
            <input value={value.databaseHost} onChange={update("databaseHost")} required />
          </label>
          <label>
            <span>Имя базы данных</span>
            <small className="field-help">База данных, из которой нужно снимать резервные копии.</small>
            <input value={value.databaseName} onChange={update("databaseName")} required />
          </label>
          <label>
            <span>Пользователь базы данных</span>
            <small className="field-help">Пользователь, от имени которого будет выполняться подключение к PostgreSQL.</small>
            <input value={value.databaseUsername} onChange={update("databaseUsername")} required />
          </label>
          <label>
            <span>Пароль базы данных {configuredSecrets?.databasePassword ? "(настроен)" : ""}</span>
            <small className="field-help">Пароль пользователя базы данных. Оставьте пустым, чтобы не менять уже сохранённое значение.</small>
            <input type="password" value={value.databasePassword ?? ""} onChange={update("databasePassword")} />
          </label>
          <label>
            <span>S3 endpoint</span>
            <small className="field-help">Адрес S3-совместимого хранилища, в которое будут отправляться резервные копии.</small>
            <input value={value.destinationAwsEndpoint} onChange={update("destinationAwsEndpoint")} required />
          </label>
          <label>
            <span>S3 bucket</span>
            <small className="field-help">Bucket, в котором будут храниться файлы резервных копий.</small>
            <input value={value.destinationAwsBucketName} onChange={update("destinationAwsBucketName")} required />
          </label>
          <label>
            <span>S3 access key</span>
            <small className="field-help">Публичный ключ доступа для подключения к S3-хранилищу.</small>
            <input value={value.destinationAwsAccessKeyId} onChange={update("destinationAwsAccessKeyId")} required />
          </label>
          <label>
            <span>S3 secret key {configuredSecrets?.destinationAwsSecretAccessKey ? "(настроен)" : ""}</span>
            <small className="field-help">Секретный ключ доступа к S3. Оставьте поле пустым, чтобы сохранить текущее значение.</small>
            <input type="password" value={value.destinationAwsSecretAccessKey ?? ""} onChange={update("destinationAwsSecretAccessKey")} />
          </label>
        </>
      ) : (
        <>
          <label>
            <span>Префикс имени архива</span>
            <small className="field-help">Префикс, который будет добавляться к имени каждого архива с данными из исходного bucket.</small>
            <input value={value.s3BackupsFilenamePrefix} onChange={update("s3BackupsFilenamePrefix")} required />
          </label>
          <label>
            <span>Source S3 endpoint</span>
            <small className="field-help">Адрес исходного S3-совместимого хранилища, из которого будут считываться файлы.</small>
            <input value={value.sourceS3AwsEndpoint} onChange={update("sourceS3AwsEndpoint")} required />
          </label>
          <label>
            <span>Source S3 bucket</span>
            <small className="field-help">Имя bucket, содержимое которого нужно архивировать.</small>
            <input value={value.sourceS3AwsBucketName} onChange={update("sourceS3AwsBucketName")} required />
          </label>
          <label>
            <span>Source S3 subfolder</span>
            <small className="field-help">Подкаталог внутри bucket, который нужно включить в архив.</small>
            <input value={value.sourceS3AwsBucketSubfolderName} onChange={update("sourceS3AwsBucketSubfolderName")} required />
          </label>
          <label>
            <span>Source S3 access key</span>
            <small className="field-help">Публичный ключ доступа к исходному S3-хранилищу.</small>
            <input value={value.sourceS3AwsAccessKeyId} onChange={update("sourceS3AwsAccessKeyId")} required />
          </label>
          <label>
            <span>Source S3 secret key {configuredSecrets?.sourceS3AwsSecretAccessKey ? "(настроен)" : ""}</span>
            <small className="field-help">Секретный ключ доступа к исходному S3. Оставьте поле пустым, чтобы сохранить текущее значение.</small>
            <input type="password" value={value.sourceS3AwsSecretAccessKey ?? ""} onChange={update("sourceS3AwsSecretAccessKey")} />
          </label>
          <label>
            <span>Destination S3 endpoint</span>
            <small className="field-help">Адрес целевого S3-совместимого хранилища, куда будет отправлен архив.</small>
            <input value={value.destinationS3AwsEndpoint} onChange={update("destinationS3AwsEndpoint")} required />
          </label>
          <label>
            <span>Destination S3 bucket</span>
            <small className="field-help">Bucket, в который будет загружен сформированный архив.</small>
            <input value={value.destinationS3AwsBucketName} onChange={update("destinationS3AwsBucketName")} required />
          </label>
          <label>
            <span>Destination S3 access key</span>
            <small className="field-help">Публичный ключ доступа к целевому S3-хранилищу.</small>
            <input value={value.destinationS3AwsAccessKeyId} onChange={update("destinationS3AwsAccessKeyId")} required />
          </label>
          <label>
            <span>Destination S3 secret key {configuredSecrets?.destinationS3AwsSecretAccessKey ? "(настроен)" : ""}</span>
            <small className="field-help">Секретный ключ доступа к целевому S3. Оставьте поле пустым, чтобы сохранить текущее значение.</small>
            <input type="password" value={value.destinationS3AwsSecretAccessKey ?? ""} onChange={update("destinationS3AwsSecretAccessKey")} />
          </label>
        </>
      )}

      <label className="toggle">
        <input type="checkbox" checked={value.enabled} onChange={(event) => onChange({ ...value, enabled: event.target.checked } as TaskPayload)} />
        <span>Включить деплой после сохранения</span>
      </label>
    </div>
  );
}
