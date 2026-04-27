import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  RecoveryEventRuleDetail,
  RecoveryEventRulePayload,
  RecoveryEventRuleUpdatePayload,
  ServiceDiscoveryResponse,
  api,
} from "../api/client";

type DiscoveryOption = {
  label: string;
  value: string;
};

type ConfiguredSecrets = {
  dbSourceSecret: boolean;
  dbTargetPassword: boolean;
  s3SourceSecret: boolean;
  s3TargetSecret: boolean;
};

const EMPTY_RULE: RecoveryEventRulePayload = {
  name: "",
  namespace: "",
  enabled: true,
  db: {
    name: "",
    dbBackupsFilenamePrefix: "",
    sourceAwsEndpoint: "",
    sourceAwsBucketName: "",
    sourceAwsAccessKeyId: "",
    sourceAwsSecretAccessKey: "",
    targetDatabaseHost: "",
    targetDatabaseName: "",
    targetDatabaseUsername: "",
    targetDatabasePassword: "",
  },
  s3: {
    name: "",
    s3BackupsFilenamePrefix: "",
    sourceS3AwsEndpoint: "",
    sourceS3AwsBucketName: "",
    sourceS3AwsAccessKeyId: "",
    sourceS3AwsSecretAccessKey: "",
    targetS3AwsEndpoint: "",
    targetS3AwsBucketName: "",
    targetS3AwsBucketSubfolderName: "",
    targetS3AwsAccessKeyId: "",
    targetS3AwsSecretAccessKey: "",
  },
};

function buildPayloadFromDetail(detail: RecoveryEventRuleDetail): RecoveryEventRulePayload {
  return {
    name: detail.name,
    namespace: detail.namespace,
    enabled: detail.enabled,
    db: {
      name: detail.db.name,
      dbBackupsFilenamePrefix: detail.db.dbBackupsFilenamePrefix,
      sourceAwsEndpoint: detail.db.sourceAwsEndpoint,
      sourceAwsBucketName: detail.db.sourceAwsBucketName,
      sourceAwsAccessKeyId: detail.db.sourceAwsAccessKeyId,
      sourceAwsSecretAccessKey: "",
      targetDatabaseHost: detail.db.targetDatabaseHost,
      targetDatabaseName: detail.db.targetDatabaseName,
      targetDatabaseUsername: detail.db.targetDatabaseUsername,
      targetDatabasePassword: "",
    },
    s3: {
      name: detail.s3.name,
      s3BackupsFilenamePrefix: detail.s3.s3BackupsFilenamePrefix,
      sourceS3AwsEndpoint: detail.s3.sourceS3AwsEndpoint,
      sourceS3AwsBucketName: detail.s3.sourceS3AwsBucketName,
      sourceS3AwsAccessKeyId: detail.s3.sourceS3AwsAccessKeyId,
      sourceS3AwsSecretAccessKey: "",
      targetS3AwsEndpoint: detail.s3.targetS3AwsEndpoint,
      targetS3AwsBucketName: detail.s3.targetS3AwsBucketName,
      targetS3AwsBucketSubfolderName: detail.s3.targetS3AwsBucketSubfolderName,
      targetS3AwsAccessKeyId: detail.s3.targetS3AwsAccessKeyId,
      targetS3AwsSecretAccessKey: "",
    },
  };
}

function buildConfiguredSecrets(detail: RecoveryEventRuleDetail): ConfiguredSecrets {
  return {
    dbSourceSecret: detail.db.hasSourceAwsSecretAccessKey,
    dbTargetPassword: detail.db.hasTargetDatabasePassword,
    s3SourceSecret: detail.s3.hasSourceS3AwsSecretAccessKey,
    s3TargetSecret: detail.s3.hasTargetS3AwsSecretAccessKey,
  };
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

export function RecoveryRuleFormPage() {
  const navigate = useNavigate();
  const { ruleId } = useParams();
  const isEditMode = Boolean(ruleId);
  const [value, setValue] = useState<RecoveryEventRulePayload>(EMPTY_RULE);
  const [namespaces, setNamespaces] = useState<string[]>([]);
  const [configuredSecrets, setConfiguredSecrets] = useState<ConfiguredSecrets>({
    dbSourceSecret: false,
    dbTargetPassword: false,
    s3SourceSecret: false,
    s3TargetSecret: false,
  });
  const [serviceDiscovery, setServiceDiscovery] = useState<ServiceDiscoveryResponse>({ services: [] });
  const [serviceDiscoveryLoading, setServiceDiscoveryLoading] = useState(false);
  const [serviceDiscoveryError, setServiceDiscoveryError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [{ namespaces: namespaceList }, detail] = await Promise.all([
          api.listNamespaces(),
          ruleId ? api.getRecoveryRule(ruleId) : Promise.resolve(null),
        ]);
        setNamespaces(namespaceList);
        if (detail) {
          setValue(buildPayloadFromDetail(detail));
          setConfiguredSecrets(buildConfiguredSecrets(detail));
        } else {
          setValue(EMPTY_RULE);
          setConfiguredSecrets({
            dbSourceSecret: false,
            dbTargetPassword: false,
            s3SourceSecret: false,
            s3TargetSecret: false,
          });
        }
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Не удалось загрузить форму recovery rule");
      }
    }

    void load();
  }, [ruleId]);

  useEffect(() => {
    if (!value.namespace) {
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
  }, [value.namespace]);

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

  function setDb<K extends keyof RecoveryEventRulePayload["db"]>(key: K, nextValue: RecoveryEventRulePayload["db"][K]) {
    setValue((current) => ({ ...current, db: { ...current.db, [key]: nextValue } }));
  }

  function setS3<K extends keyof RecoveryEventRulePayload["s3"]>(key: K, nextValue: RecoveryEventRulePayload["s3"][K]) {
    setValue((current) => ({ ...current, s3: { ...current.s3, [key]: nextValue } }));
  }

  function buildSubmitPayload(): RecoveryEventRulePayload | RecoveryEventRuleUpdatePayload {
    const payload: RecoveryEventRulePayload = {
      ...value,
      db: { ...value.db },
      s3: { ...value.s3 },
    };

    if (!payload.db.sourceAwsSecretAccessKey) {
      delete payload.db.sourceAwsSecretAccessKey;
    }
    if (!payload.db.targetDatabasePassword) {
      delete payload.db.targetDatabasePassword;
    }
    if (!payload.s3.sourceS3AwsSecretAccessKey) {
      delete payload.s3.sourceS3AwsSecretAccessKey;
    }
    if (!payload.s3.targetS3AwsSecretAccessKey) {
      delete payload.s3.targetS3AwsSecretAccessKey;
    }

    return payload;
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();

    try {
      const payload = buildSubmitPayload();
      if (ruleId) {
        await api.updateRecoveryRule(ruleId, payload);
        navigate(`/recovery-rules/${ruleId}`);
      } else {
        const rule = await api.createRecoveryRule(payload as RecoveryEventRulePayload);
        navigate(`/recovery-rules/${rule.id}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сохранить recovery rule");
    }
  }

  const dbHostOptions = useMemo(() => buildDbHostOptions(serviceDiscovery), [serviceDiscovery]);
  const s3EndpointOptions = useMemo(() => buildS3EndpointOptions(serviceDiscovery), [serviceDiscovery]);
  const serviceDiscoveryPlaceholder = !value.namespace
    ? "Сначала выберите namespace"
    : serviceDiscoveryLoading
      ? "Загружаем сервисы..."
      : "Подставить из Service Discovery";
  const serviceDiscoveryEnabled = Boolean(value.namespace) && !serviceDiscoveryLoading;

  return (
    <section className="stack">
      <div className="toolbar">
        <div>
          <h2>{isEditMode ? "Редактирование recovery rule" : "Создание recovery rule"}</h2>
          <p className="subtle">Правило полностью владеет event-based конфигом DB restore + S3 restore в общем namespace.</p>
        </div>
        <Link className="button ghost" to={ruleId ? `/recovery-rules/${ruleId}` : "/recovery-rules"}>
          Отмена
        </Link>
      </div>

      {error ? <div className="alert">{error}</div> : null}

      <form className="stack" onSubmit={(event) => void handleSubmit(event)}>
        <div className="card form-grid">
          <label>
            <span>Название правила</span>
            <input value={value.name} onChange={(event) => setValue((current) => ({ ...current, name: event.target.value }))} required />
          </label>
          <label>
            <span>Namespace</span>
            <small className="field-help">Оба managed restore service будут задеплоены в этот namespace.</small>
            <div className="namespace-field">
              <select value={value.namespace} onChange={(event) => setValue((current) => ({ ...current, namespace: event.target.value }))}>
                <option value="">Выберите namespace</option>
                {namespaces.map((namespace) => (
                  <option key={namespace} value={namespace}>
                    {namespace}
                  </option>
                ))}
              </select>
              <button type="button" className="button ghost" onClick={() => void handleCreateNamespace()}>
                Создать namespace
              </button>
            </div>
            {serviceDiscoveryError ? <small className="field-help discovery-note">Service Discovery: {serviceDiscoveryError}</small> : null}
          </label>
          <label className="toggle">
            <input type="checkbox" checked={value.enabled} onChange={(event) => setValue((current) => ({ ...current, enabled: event.target.checked }))} />
            <span>Включить recovery rule</span>
          </label>
        </div>

        <div className="card form-grid">
          <h3>DB restore</h3>
          <label>
            <span>Имя DB restore</span>
            <input value={value.db.name} onChange={(event) => setDb("name", event.target.value)} required />
          </label>
          <label>
            <span>Backup prefix</span>
            <input value={value.db.dbBackupsFilenamePrefix} onChange={(event) => setDb("dbBackupsFilenamePrefix", event.target.value)} required />
          </label>
          <label>
            <span>Backup S3 endpoint</span>
            <div className="discovery-field">
              <input value={value.db.sourceAwsEndpoint} onChange={(event) => setDb("sourceAwsEndpoint", event.target.value)} required />
              <DiscoverySelect
                ariaLabel="Service Discovery: DB backup source"
                placeholder={serviceDiscoveryPlaceholder}
                options={s3EndpointOptions}
                disabled={!serviceDiscoveryEnabled || s3EndpointOptions.length === 0}
                onSelect={(nextValue) => setDb("sourceAwsEndpoint", nextValue)}
              />
            </div>
          </label>
          <label>
            <span>Backup S3 bucket</span>
            <input value={value.db.sourceAwsBucketName} onChange={(event) => setDb("sourceAwsBucketName", event.target.value)} required />
          </label>
          <label>
            <span>Backup S3 access key</span>
            <input value={value.db.sourceAwsAccessKeyId} onChange={(event) => setDb("sourceAwsAccessKeyId", event.target.value)} required />
          </label>
          <label>
            <span>Backup S3 secret key {configuredSecrets.dbSourceSecret ? "(настроен)" : ""}</span>
            <input type="password" value={value.db.sourceAwsSecretAccessKey ?? ""} onChange={(event) => setDb("sourceAwsSecretAccessKey", event.target.value)} required={!isEditMode} />
          </label>
          <label>
            <span>Target DB host</span>
            <div className="discovery-field">
              <input value={value.db.targetDatabaseHost} onChange={(event) => setDb("targetDatabaseHost", event.target.value)} required />
              <DiscoverySelect
                ariaLabel="Service Discovery: target DB host"
                placeholder={serviceDiscoveryPlaceholder}
                options={dbHostOptions}
                disabled={!serviceDiscoveryEnabled || dbHostOptions.length === 0}
                onSelect={(nextValue) => setDb("targetDatabaseHost", nextValue)}
              />
            </div>
          </label>
          <label>
            <span>Target DB name</span>
            <input value={value.db.targetDatabaseName} onChange={(event) => setDb("targetDatabaseName", event.target.value)} required />
          </label>
          <label>
            <span>Target DB user</span>
            <input value={value.db.targetDatabaseUsername} onChange={(event) => setDb("targetDatabaseUsername", event.target.value)} required />
          </label>
          <label>
            <span>Target DB password {configuredSecrets.dbTargetPassword ? "(настроен)" : ""}</span>
            <input type="password" value={value.db.targetDatabasePassword ?? ""} onChange={(event) => setDb("targetDatabasePassword", event.target.value)} required={!isEditMode} />
          </label>
        </div>

        <div className="card form-grid">
          <h3>S3 restore</h3>
          <label>
            <span>Имя S3 restore</span>
            <input value={value.s3.name} onChange={(event) => setS3("name", event.target.value)} required />
          </label>
          <label>
            <span>Backup prefix</span>
            <input value={value.s3.s3BackupsFilenamePrefix} onChange={(event) => setS3("s3BackupsFilenamePrefix", event.target.value)} required />
          </label>
          <label>
            <span>Backup source endpoint</span>
            <div className="discovery-field">
              <input value={value.s3.sourceS3AwsEndpoint} onChange={(event) => setS3("sourceS3AwsEndpoint", event.target.value)} required />
              <DiscoverySelect
                ariaLabel="Service Discovery: recovery source S3"
                placeholder={serviceDiscoveryPlaceholder}
                options={s3EndpointOptions}
                disabled={!serviceDiscoveryEnabled || s3EndpointOptions.length === 0}
                onSelect={(nextValue) => setS3("sourceS3AwsEndpoint", nextValue)}
              />
            </div>
          </label>
          <label>
            <span>Backup source bucket</span>
            <input value={value.s3.sourceS3AwsBucketName} onChange={(event) => setS3("sourceS3AwsBucketName", event.target.value)} required />
          </label>
          <label>
            <span>Backup source access key</span>
            <input value={value.s3.sourceS3AwsAccessKeyId} onChange={(event) => setS3("sourceS3AwsAccessKeyId", event.target.value)} required />
          </label>
          <label>
            <span>Backup source secret key {configuredSecrets.s3SourceSecret ? "(настроен)" : ""}</span>
            <input type="password" value={value.s3.sourceS3AwsSecretAccessKey ?? ""} onChange={(event) => setS3("sourceS3AwsSecretAccessKey", event.target.value)} required={!isEditMode} />
          </label>
          <label>
            <span>Target S3 endpoint</span>
            <div className="discovery-field">
              <input value={value.s3.targetS3AwsEndpoint} onChange={(event) => setS3("targetS3AwsEndpoint", event.target.value)} required />
              <DiscoverySelect
                ariaLabel="Service Discovery: recovery target S3"
                placeholder={serviceDiscoveryPlaceholder}
                options={s3EndpointOptions}
                disabled={!serviceDiscoveryEnabled || s3EndpointOptions.length === 0}
                onSelect={(nextValue) => setS3("targetS3AwsEndpoint", nextValue)}
              />
            </div>
          </label>
          <label>
            <span>Target S3 bucket</span>
            <input value={value.s3.targetS3AwsBucketName} onChange={(event) => setS3("targetS3AwsBucketName", event.target.value)} required />
          </label>
          <label>
            <span>Target S3 subfolder</span>
            <input value={value.s3.targetS3AwsBucketSubfolderName} onChange={(event) => setS3("targetS3AwsBucketSubfolderName", event.target.value)} />
          </label>
          <label>
            <span>Target S3 access key</span>
            <input value={value.s3.targetS3AwsAccessKeyId} onChange={(event) => setS3("targetS3AwsAccessKeyId", event.target.value)} required />
          </label>
          <label>
            <span>Target S3 secret key {configuredSecrets.s3TargetSecret ? "(настроен)" : ""}</span>
            <input type="password" value={value.s3.targetS3AwsSecretAccessKey ?? ""} onChange={(event) => setS3("targetS3AwsSecretAccessKey", event.target.value)} required={!isEditMode} />
          </label>
        </div>

        <div className="toolbar-actions">
          <button className="button primary" type="submit">
            Сохранить recovery rule
          </button>
        </div>
      </form>
    </section>
  );
}
