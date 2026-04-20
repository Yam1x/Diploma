import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  BackupEventRuleDetail,
  BackupEventRulePayload,
  BackupEventRuleUpdatePayload,
  ServiceDiscoveryResponse,
  api,
} from "../api/client";

type DiscoveryOption = {
  label: string;
  value: string;
};

type ConfiguredSecrets = {
  dbPassword: boolean;
  dbDestinationSecret: boolean;
  s3SourceSecret: boolean;
  s3DestinationSecret: boolean;
};

const EMPTY_RULE: BackupEventRulePayload = {
  name: "",
  namespace: "",
  enabled: true,
  db: {
    name: "",
    dbBackupsFilenamePrefix: "",
    databaseHost: "",
    databaseName: "",
    databaseUsername: "",
    databasePassword: "",
    destinationAwsEndpoint: "",
    destinationAwsBucketName: "",
    destinationAwsAccessKeyId: "",
    destinationAwsSecretAccessKey: "",
  },
  s3: {
    name: "",
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
  },
};

function buildPayloadFromDetail(detail: BackupEventRuleDetail): BackupEventRulePayload {
  return {
    name: detail.name,
    namespace: detail.namespace,
    enabled: detail.enabled,
    db: {
      name: detail.db.name,
      dbBackupsFilenamePrefix: detail.db.dbBackupsFilenamePrefix,
      databaseHost: detail.db.databaseHost,
      databaseName: detail.db.databaseName,
      databaseUsername: detail.db.databaseUsername,
      databasePassword: "",
      destinationAwsEndpoint: detail.db.destinationAwsEndpoint,
      destinationAwsBucketName: detail.db.destinationAwsBucketName,
      destinationAwsAccessKeyId: detail.db.destinationAwsAccessKeyId,
      destinationAwsSecretAccessKey: "",
    },
    s3: {
      name: detail.s3.name,
      s3BackupsFilenamePrefix: detail.s3.s3BackupsFilenamePrefix,
      sourceS3AwsEndpoint: detail.s3.sourceS3AwsEndpoint,
      sourceS3AwsAccessKeyId: detail.s3.sourceS3AwsAccessKeyId,
      sourceS3AwsBucketName: detail.s3.sourceS3AwsBucketName,
      sourceS3AwsBucketSubfolderName: detail.s3.sourceS3AwsBucketSubfolderName,
      sourceS3AwsSecretAccessKey: "",
      destinationS3AwsEndpoint: detail.s3.destinationS3AwsEndpoint,
      destinationS3AwsAccessKeyId: detail.s3.destinationS3AwsAccessKeyId,
      destinationS3AwsBucketName: detail.s3.destinationS3AwsBucketName,
      destinationS3AwsSecretAccessKey: "",
    },
  };
}

function buildConfiguredSecrets(detail: BackupEventRuleDetail): ConfiguredSecrets {
  return {
    dbPassword: detail.db.hasDatabasePassword,
    dbDestinationSecret: detail.db.hasDestinationAwsSecretAccessKey,
    s3SourceSecret: detail.s3.hasSourceS3AwsSecretAccessKey,
    s3DestinationSecret: detail.s3.hasDestinationS3AwsSecretAccessKey,
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

export function EventRuleFormPage() {
  const navigate = useNavigate();
  const { ruleId } = useParams();
  const isEditMode = Boolean(ruleId);
  const [value, setValue] = useState<BackupEventRulePayload>(EMPTY_RULE);
  const [namespaces, setNamespaces] = useState<string[]>([]);
  const [configuredSecrets, setConfiguredSecrets] = useState<ConfiguredSecrets>({
    dbPassword: false,
    dbDestinationSecret: false,
    s3SourceSecret: false,
    s3DestinationSecret: false,
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
          ruleId ? api.getEventRule(ruleId) : Promise.resolve(null),
        ]);
        setNamespaces(namespaceList);
        if (detail) {
          setValue(buildPayloadFromDetail(detail));
          setConfiguredSecrets(buildConfiguredSecrets(detail));
        } else {
          setValue(EMPTY_RULE);
          setConfiguredSecrets({
            dbPassword: false,
            dbDestinationSecret: false,
            s3SourceSecret: false,
            s3DestinationSecret: false,
          });
        }
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РіСЂСѓР·РёС‚СЊ С„РѕСЂРјСѓ event rule");
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
        setServiceDiscoveryError(err instanceof Error ? err.message : "РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РіСЂСѓР·РёС‚СЊ service discovery");
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
    const name = window.prompt("Р’РІРµРґРёС‚Рµ РёРјСЏ namespace");
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
      setError(err instanceof Error ? err.message : "РќРµ СѓРґР°Р»РѕСЃСЊ СЃРѕР·РґР°С‚СЊ namespace");
    }
  }

  function setDb<K extends keyof BackupEventRulePayload["db"]>(key: K, nextValue: BackupEventRulePayload["db"][K]) {
    setValue((current) => ({ ...current, db: { ...current.db, [key]: nextValue } }));
  }

  function setS3<K extends keyof BackupEventRulePayload["s3"]>(key: K, nextValue: BackupEventRulePayload["s3"][K]) {
    setValue((current) => ({ ...current, s3: { ...current.s3, [key]: nextValue } }));
  }

  function buildSubmitPayload(): BackupEventRulePayload | BackupEventRuleUpdatePayload {
    const payload: BackupEventRulePayload = {
      ...value,
      db: { ...value.db },
      s3: { ...value.s3 },
    };

    if (!payload.db.databasePassword) {
      delete payload.db.databasePassword;
    }
    if (!payload.db.destinationAwsSecretAccessKey) {
      delete payload.db.destinationAwsSecretAccessKey;
    }
    if (!payload.s3.sourceS3AwsSecretAccessKey) {
      delete payload.s3.sourceS3AwsSecretAccessKey;
    }
    if (!payload.s3.destinationS3AwsSecretAccessKey) {
      delete payload.s3.destinationS3AwsSecretAccessKey;
    }

    return payload;
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();

    try {
      const payload = buildSubmitPayload();
      if (ruleId) {
        await api.updateEventRule(ruleId, payload);
        navigate(`/event-rules/${ruleId}`);
      } else {
        const rule = await api.createEventRule(payload as BackupEventRulePayload);
        navigate(`/event-rules/${rule.id}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "РќРµ СѓРґР°Р»РѕСЃСЊ СЃРѕС…СЂР°РЅРёС‚СЊ event rule");
    }
  }

  const dbHostOptions = useMemo(() => buildDbHostOptions(serviceDiscovery), [serviceDiscovery]);
  const s3EndpointOptions = useMemo(() => buildS3EndpointOptions(serviceDiscovery), [serviceDiscovery]);
  const serviceDiscoveryPlaceholder = !value.namespace
    ? "РЎРЅР°С‡Р°Р»Р° РІС‹Р±РµСЂРёС‚Рµ namespace"
    : serviceDiscoveryLoading
      ? "Р—Р°РіСЂСѓР¶Р°РµРј СЃРµСЂРІРёСЃС‹..."
      : "РџРѕРґСЃС‚Р°РІРёС‚СЊ РёР· Service Discovery";
  const serviceDiscoveryEnabled = Boolean(value.namespace) && !serviceDiscoveryLoading;

  return (
    <section className="stack">
      <div className="toolbar">
        <div>
          <h2>{isEditMode ? "Р РµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ event rule" : "РЎРѕР·РґР°РЅРёРµ event rule"}</h2>
          <p className="subtle">РџСЂР°РІРёР»Рѕ РїРѕР»РЅРѕСЃС‚СЊСЋ РІР»Р°РґРµРµС‚ event-based РєРѕРЅС„РёРіРѕРј DB + S3 РІ РѕР±С‰РµРј namespace.</p>
        </div>
        <Link className="button ghost" to={ruleId ? `/event-rules/${ruleId}` : "/event-rules"}>
          РћС‚РјРµРЅР°
        </Link>
      </div>

      {error ? <div className="alert">{error}</div> : null}

      <form className="stack" onSubmit={(event) => void handleSubmit(event)}>
        <div className="card form-grid">
          <label>
            <span>РќР°Р·РІР°РЅРёРµ РїСЂР°РІРёР»Р°</span>
            <input value={value.name} onChange={(event) => setValue((current) => ({ ...current, name: event.target.value }))} required />
          </label>
          <label>
            <span>Namespace</span>
            <small className="field-help">РћР±Р° managed backup service Р±СѓРґСѓС‚ Р·Р°РґРµРїР»РѕРµРЅС‹ РІ СЌС‚РѕС‚ namespace.</small>
            <div className="namespace-field">
              <select value={value.namespace} onChange={(event) => setValue((current) => ({ ...current, namespace: event.target.value }))}>
                <option value="">Р’С‹Р±РµСЂРёС‚Рµ namespace</option>
                {namespaces.map((namespace) => (
                  <option key={namespace} value={namespace}>
                    {namespace}
                  </option>
                ))}
              </select>
              <button type="button" className="button ghost" onClick={() => void handleCreateNamespace()}>
                РЎРѕР·РґР°С‚СЊ namespace
              </button>
            </div>
            {serviceDiscoveryError ? <small className="field-help discovery-note">Service Discovery: {serviceDiscoveryError}</small> : null}
          </label>
          <label className="toggle">
            <input type="checkbox" checked={value.enabled} onChange={(event) => setValue((current) => ({ ...current, enabled: event.target.checked }))} />
            <span>Р’РєР»СЋС‡РёС‚СЊ event rule</span>
          </label>
        </div>

        <div className="card form-grid">
          <h3>DB backup</h3>
          <label>
            <span>РРјСЏ DB backup</span>
            <input value={value.db.name} onChange={(event) => setDb("name", event.target.value)} required />
          </label>
          <label>
            <span>РџСЂРµС„РёРєСЃ РёРјРµРЅРё С„Р°Р№Р»Р°</span>
            <input value={value.db.dbBackupsFilenamePrefix} onChange={(event) => setDb("dbBackupsFilenamePrefix", event.target.value)} required />
          </label>
          <label>
            <span>РҐРѕСЃС‚ Р±Р°Р·С‹ РґР°РЅРЅС‹С…</span>
            <div className="discovery-field">
              <input value={value.db.databaseHost} onChange={(event) => setDb("databaseHost", event.target.value)} required />
              <DiscoverySelect
                ariaLabel="Service Discovery: DB host"
                placeholder={serviceDiscoveryPlaceholder}
                options={dbHostOptions}
                disabled={!serviceDiscoveryEnabled || dbHostOptions.length === 0}
                onSelect={(nextValue) => setDb("databaseHost", nextValue)}
              />
            </div>
          </label>
          <label>
            <span>РРјСЏ Р±Р°Р·С‹ РґР°РЅРЅС‹С…</span>
            <input value={value.db.databaseName} onChange={(event) => setDb("databaseName", event.target.value)} required />
          </label>
          <label>
            <span>РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ Р±Р°Р·С‹ РґР°РЅРЅС‹С…</span>
            <input value={value.db.databaseUsername} onChange={(event) => setDb("databaseUsername", event.target.value)} required />
          </label>
          <label>
            <span>РџР°СЂРѕР»СЊ Р±Р°Р·С‹ РґР°РЅРЅС‹С… {configuredSecrets.dbPassword ? "(РЅР°СЃС‚СЂРѕРµРЅ)" : ""}</span>
            <input type="password" value={value.db.databasePassword ?? ""} onChange={(event) => setDb("databasePassword", event.target.value)} required={!isEditMode} />
          </label>
          <label>
            <span>S3 endpoint</span>
            <div className="discovery-field">
              <input value={value.db.destinationAwsEndpoint} onChange={(event) => setDb("destinationAwsEndpoint", event.target.value)} required />
              <DiscoverySelect
                ariaLabel="Service Discovery: DB destination S3"
                placeholder={serviceDiscoveryPlaceholder}
                options={s3EndpointOptions}
                disabled={!serviceDiscoveryEnabled || s3EndpointOptions.length === 0}
                onSelect={(nextValue) => setDb("destinationAwsEndpoint", nextValue)}
              />
            </div>
          </label>
          <label>
            <span>S3 bucket</span>
            <input value={value.db.destinationAwsBucketName} onChange={(event) => setDb("destinationAwsBucketName", event.target.value)} required />
          </label>
          <label>
            <span>S3 access key</span>
            <input value={value.db.destinationAwsAccessKeyId} onChange={(event) => setDb("destinationAwsAccessKeyId", event.target.value)} required />
          </label>
          <label>
            <span>S3 secret key {configuredSecrets.dbDestinationSecret ? "(РЅР°СЃС‚СЂРѕРµРЅ)" : ""}</span>
            <input
              type="password"
              value={value.db.destinationAwsSecretAccessKey ?? ""}
              onChange={(event) => setDb("destinationAwsSecretAccessKey", event.target.value)}
              required={!isEditMode}
            />
          </label>
        </div>

        <div className="card form-grid">
          <h3>S3 backup</h3>
          <label>
            <span>РРјСЏ S3 backup</span>
            <input value={value.s3.name} onChange={(event) => setS3("name", event.target.value)} required />
          </label>
          <label>
            <span>РџСЂРµС„РёРєСЃ РёРјРµРЅРё Р°СЂС…РёРІР°</span>
            <input value={value.s3.s3BackupsFilenamePrefix} onChange={(event) => setS3("s3BackupsFilenamePrefix", event.target.value)} required />
          </label>
          <label>
            <span>Source S3 endpoint</span>
            <div className="discovery-field">
              <input value={value.s3.sourceS3AwsEndpoint} onChange={(event) => setS3("sourceS3AwsEndpoint", event.target.value)} required />
              <DiscoverySelect
                ariaLabel="Service Discovery: source S3"
                placeholder={serviceDiscoveryPlaceholder}
                options={s3EndpointOptions}
                disabled={!serviceDiscoveryEnabled || s3EndpointOptions.length === 0}
                onSelect={(nextValue) => setS3("sourceS3AwsEndpoint", nextValue)}
              />
            </div>
          </label>
          <label>
            <span>Source S3 bucket</span>
            <input value={value.s3.sourceS3AwsBucketName} onChange={(event) => setS3("sourceS3AwsBucketName", event.target.value)} required />
          </label>
          <label>
            <span>Source S3 subfolder</span>
            <input value={value.s3.sourceS3AwsBucketSubfolderName} onChange={(event) => setS3("sourceS3AwsBucketSubfolderName", event.target.value)} />
          </label>
          <label>
            <span>Source S3 access key</span>
            <input value={value.s3.sourceS3AwsAccessKeyId} onChange={(event) => setS3("sourceS3AwsAccessKeyId", event.target.value)} required />
          </label>
          <label>
            <span>Source S3 secret key {configuredSecrets.s3SourceSecret ? "(РЅР°СЃС‚СЂРѕРµРЅ)" : ""}</span>
            <input
              type="password"
              value={value.s3.sourceS3AwsSecretAccessKey ?? ""}
              onChange={(event) => setS3("sourceS3AwsSecretAccessKey", event.target.value)}
              required={!isEditMode}
            />
          </label>
          <label>
            <span>Destination S3 endpoint</span>
            <div className="discovery-field">
              <input value={value.s3.destinationS3AwsEndpoint} onChange={(event) => setS3("destinationS3AwsEndpoint", event.target.value)} required />
              <DiscoverySelect
                ariaLabel="Service Discovery: destination S3"
                placeholder={serviceDiscoveryPlaceholder}
                options={s3EndpointOptions}
                disabled={!serviceDiscoveryEnabled || s3EndpointOptions.length === 0}
                onSelect={(nextValue) => setS3("destinationS3AwsEndpoint", nextValue)}
              />
            </div>
          </label>
          <label>
            <span>Destination S3 bucket</span>
            <input value={value.s3.destinationS3AwsBucketName} onChange={(event) => setS3("destinationS3AwsBucketName", event.target.value)} required />
          </label>
          <label>
            <span>Destination S3 access key</span>
            <input value={value.s3.destinationS3AwsAccessKeyId} onChange={(event) => setS3("destinationS3AwsAccessKeyId", event.target.value)} required />
          </label>
          <label>
            <span>Destination S3 secret key {configuredSecrets.s3DestinationSecret ? "(РЅР°СЃС‚СЂРѕРµРЅ)" : ""}</span>
            <input
              type="password"
              value={value.s3.destinationS3AwsSecretAccessKey ?? ""}
              onChange={(event) => setS3("destinationS3AwsSecretAccessKey", event.target.value)}
              required={!isEditMode}
            />
          </label>
        </div>

        <div className="toolbar-actions">
          <button className="button primary" type="submit">
            РЎРѕС…СЂР°РЅРёС‚СЊ event rule
          </button>
        </div>
      </form>
    </section>
  );
}
