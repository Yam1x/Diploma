import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { BackupEventRuleDetail, api } from "../api/client";

function formatBoolean(value: boolean) {
  return value ? "Р”Р°" : "РќРµС‚";
}

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString() : "РќРёРєРѕРіРґР°";
}

function formatConfigured(value: boolean) {
  return value ? "РќР°СЃС‚СЂРѕРµРЅРѕ" : "РќРµС‚";
}

function formatEventWatcherStatus(status: string) {
  const labels: Record<string, string> = {
    disabled: "Р’С‹РєР»СЋС‡РµРЅРѕ",
    waiting_for_baseline: "РРЅРёС†РёР°Р»РёР·Р°С†РёСЏ baseline",
    watching: "РћС‚СЃР»РµР¶РёРІР°РµС‚ РёР·РјРµРЅРµРЅРёСЏ",
    cooldown: "Cooldown",
    error: "РћС€РёР±РєР°",
  };

  return labels[status] ?? status;
}

export function EventRuleDetailsPage() {
  const { ruleId } = useParams();
  const navigate = useNavigate();
  const [rule, setRule] = useState<BackupEventRuleDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!ruleId) {
      return;
    }
    try {
      const detail = await api.getEventRule(ruleId);
      setRule(detail);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РіСЂСѓР·РёС‚СЊ event rule");
    }
  }

  useEffect(() => {
    void load();
  }, [ruleId]);

  async function runAction(action: () => Promise<BackupEventRuleDetail | void>) {
    try {
      await action();
      await load();
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "РќРµ СѓРґР°Р»РѕСЃСЊ РІС‹РїРѕР»РЅРёС‚СЊ РґРµР№СЃС‚РІРёРµ");
    }
  }

  async function handleDelete() {
    if (!ruleId || !rule) {
      return;
    }
    if (!window.confirm(`РЈРґР°Р»РёС‚СЊ event rule "${rule.name}"?`)) {
      return;
    }
    try {
      await api.deleteEventRule(ruleId);
      navigate("/event-rules");
    } catch (err) {
      setError(err instanceof Error ? err.message : "РќРµ СѓРґР°Р»РѕСЃСЊ СѓРґР°Р»РёС‚СЊ event rule");
    }
  }

  if (!rule) {
    return <section className="stack">{error ? <div className="alert">{error}</div> : <p>Р—Р°РіСЂСѓР·РєР°...</p>}</section>;
  }

  return (
    <section className="stack">
      <div className="toolbar">
        <div>
          <h2>{rule.name}</h2>
          <p className="subtle">Event rule РІР»Р°РґРµРµС‚ РїР°СЂРѕР№ managed backup service РІ namespace `{rule.namespace}`.</p>
        </div>
        <div className="toolbar-actions">
          <Link className="button ghost" to={`/event-rules/${rule.id}/edit`}>
            РР·РјРµРЅРёС‚СЊ
          </Link>
          <button className="button primary" onClick={() => void runAction(() => api.runEventRule(String(rule.id)))}>
            Р—Р°РїСѓСЃС‚РёС‚СЊ СЃРµР№С‡Р°СЃ
          </button>
          {rule.enabled ? (
            <button className="button danger" onClick={() => void runAction(() => api.disableEventRule(String(rule.id)))}>
              Р’С‹РєР»СЋС‡РёС‚СЊ
            </button>
          ) : (
            <button className="button primary" onClick={() => void runAction(() => api.enableEventRule(String(rule.id)))}>
              Р’РєР»СЋС‡РёС‚СЊ
            </button>
          )}
          <button className="button ghost" onClick={() => void handleDelete()}>
            РЈРґР°Р»РёС‚СЊ
          </button>
        </div>
      </div>

      {error ? <div className="alert">{error}</div> : null}

      <div className="details-grid">
        <article className="card">
          <h3>РЎРѕСЃС‚РѕСЏРЅРёРµ</h3>
          <dl>
            <dt>Р’РєР»СЋС‡РµРЅРѕ</dt>
            <dd>{formatBoolean(rule.enabled)}</dd>
            <dt>Namespace</dt>
            <dd>{rule.namespace}</dd>
            <dt>DB backup</dt>
            <dd>{rule.db.name}</dd>
            <dt>S3 backup</dt>
            <dd>{rule.s3.name}</dd>
            <dt>Watcher</dt>
            <dd>{formatEventWatcherStatus(rule.eventWatcherStatus)}</dd>
          </dl>
        </article>
        <article className="card">
          <h3>РЎРѕР±С‹С‚РёСЏ watcher</h3>
          <dl>
            <dt>РџРѕСЃР»РµРґРЅРёР№ poll</dt>
            <dd>{formatDate(rule.lastPolledAt)}</dd>
            <dt>DB change</dt>
            <dd>{formatDate(rule.lastDbChangeAt)}</dd>
            <dt>S3 change</dt>
            <dd>{formatDate(rule.lastS3ChangeAt)}</dd>
            <dt>Combined run</dt>
            <dd>{formatDate(rule.lastTriggeredAt)}</dd>
            <dt>РџРѕСЃР»РµРґРЅСЏСЏ РѕС€РёР±РєР°</dt>
            <dd>{rule.lastErrorMessage ?? "РќРµС‚"}</dd>
          </dl>
        </article>
      </div>

      <div className="details-grid">
        <article className="card">
          <h3>DB backup config</h3>
          <dl>
            <dt>РҐРѕСЃС‚ Р±Р°Р·С‹ РґР°РЅРЅС‹С…</dt>
            <dd>{rule.db.databaseHost}</dd>
            <dt>РРјСЏ Р±Р°Р·С‹ РґР°РЅРЅС‹С…</dt>
            <dd>{rule.db.databaseName}</dd>
            <dt>РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ</dt>
            <dd>{rule.db.databaseUsername}</dd>
            <dt>РџСЂРµС„РёРєСЃ С„Р°Р№Р»Р°</dt>
            <dd>{rule.db.dbBackupsFilenamePrefix}</dd>
            <dt>Destination endpoint</dt>
            <dd>{rule.db.destinationAwsEndpoint}</dd>
            <dt>Destination bucket</dt>
            <dd>{rule.db.destinationAwsBucketName}</dd>
            <dt>Destination access key</dt>
            <dd>{rule.db.destinationAwsAccessKeyId}</dd>
            <dt>DB password</dt>
            <dd>{formatConfigured(rule.db.hasDatabasePassword)}</dd>
            <dt>Destination secret</dt>
            <dd>{formatConfigured(rule.db.hasDestinationAwsSecretAccessKey)}</dd>
          </dl>
        </article>
        <article className="card">
          <h3>S3 backup config</h3>
          <dl>
            <dt>Source endpoint</dt>
            <dd>{rule.s3.sourceS3AwsEndpoint}</dd>
            <dt>Source bucket</dt>
            <dd>{rule.s3.sourceS3AwsBucketName}</dd>
            <dt>Source subfolder</dt>
            <dd>{rule.s3.sourceS3AwsBucketSubfolderName || "Р’РµСЃСЊ bucket"}</dd>
            <dt>Destination endpoint</dt>
            <dd>{rule.s3.destinationS3AwsEndpoint}</dd>
            <dt>Destination bucket</dt>
            <dd>{rule.s3.destinationS3AwsBucketName}</dd>
            <dt>Source access key</dt>
            <dd>{rule.s3.sourceS3AwsAccessKeyId}</dd>
            <dt>Destination access key</dt>
            <dd>{rule.s3.destinationS3AwsAccessKeyId}</dd>
            <dt>Source secret</dt>
            <dd>{formatConfigured(rule.s3.hasSourceS3AwsSecretAccessKey)}</dd>
            <dt>Destination secret</dt>
            <dd>{formatConfigured(rule.s3.hasDestinationS3AwsSecretAccessKey)}</dd>
          </dl>
        </article>
      </div>
    </section>
  );
}
