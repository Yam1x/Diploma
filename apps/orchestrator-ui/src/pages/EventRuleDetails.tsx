import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { BackupEventRuleDetail, api } from "../api/client";

function formatBoolean(value: boolean) {
  return value ? "Р”Р°" : "РќРµС‚";
}

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString() : "РќРёРєРѕРіРґР°";
}

function formatEventWatcherStatus(status: string) {
  const labels: Record<string, string> = {
    disabled: "Р’С‹РєР»СЋС‡РµРЅР°",
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
          <p className="subtle">Combined event rule РґР»СЏ РїР°СЂРЅРѕРіРѕ backup DB + S3.</p>
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
            <dt>DB task</dt>
            <dd>{rule.dbTaskName}</dd>
            <dt>S3 task</dt>
            <dd>{rule.s3TaskName}</dd>
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
    </section>
  );
}
