import { ChangeEvent } from "react";

import { TaskPayload } from "../api/client";

type Props = {
  value: TaskPayload;
  onChange: (next: TaskPayload) => void;
  namespaceOptions: string[];
  passwordConfigured?: boolean;
  secretConfigured?: boolean;
  onCreateNamespace?: () => void;
};

export function TaskFormFields({ value, onChange, namespaceOptions, passwordConfigured, secretConfigured, onCreateNamespace }: Props) {
  const update = (key: keyof TaskPayload) => (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    onChange({ ...value, [key]: event.target.value });
  };

  return (
    <div className="stack">
      <section className="card form-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">General</p>
            <h3>Общие параметры</h3>
          </div>
          <p className="subtle">Название задачи, целевой namespace и базовое поведение релиза.</p>
        </div>
        <div className="form-grid">
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
                Создать
              </button>
            </div>
          </label>
          <label>
            <span>Расписание</span>
            <small className="field-help">Cron-выражение, определяющее частоту запуска резервного копирования.</small>
            <input value={value.schedule} onChange={update("schedule")} placeholder="0 * * * *" required />
          </label>
          <label>
            <span>Префикс имени файла</span>
            <small className="field-help">Префикс, который будет добавляться к имени каждого созданного дампа.</small>
            <input value={value.dbBackupsFilenamePrefix} onChange={update("dbBackupsFilenamePrefix")} required />
          </label>
          <label className="toggle">
            <input
              type="checkbox"
              checked={value.enabled}
              onChange={(event) => onChange({ ...value, enabled: event.target.checked })}
            />
            <span>Включить деплой после сохранения</span>
          </label>
        </div>
      </section>

      <section className="card form-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Database</p>
            <h3>Подключение к PostgreSQL</h3>
          </div>
          <p className="subtle">Параметры, с которыми backup job будет снимать дамп базы данных.</p>
        </div>
        <div className="form-grid">
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
            <span>Пароль базы данных {passwordConfigured ? "(настроен)" : ""}</span>
            <small className="field-help">Оставьте пустым, чтобы не менять уже сохранённое значение.</small>
            <input type="password" value={value.databasePassword ?? ""} onChange={update("databasePassword")} />
          </label>
        </div>
      </section>

      <section className="card form-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Storage</p>
            <h3>Хранилище резервных копий</h3>
          </div>
          <p className="subtle">S3-совместимое хранилище, куда будут отправляться архивы после создания.</p>
        </div>
        <div className="form-grid">
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
            <span>S3 secret key {secretConfigured ? "(настроен)" : ""}</span>
            <small className="field-help">Оставьте поле пустым, чтобы сохранить текущее значение.</small>
            <input
              type="password"
              value={value.destinationAwsSecretAccessKey ?? ""}
              onChange={update("destinationAwsSecretAccessKey")}
            />
          </label>
        </div>
      </section>
    </div>
  );
}
