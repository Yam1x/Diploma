import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { BackupEventRuleSummary, api } from "../api/client";

function formatBoolean(value: boolean) {
  return value ? "Р”Р°" : "РќРµС‚";
}

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString() : "РќРёРєРѕРіРґР°";
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

export function EventRulesListPage() {
  const [rules, setRules] = useState<BackupEventRuleSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api
      .listEventRules()
      .then((response) => {
        setRules(response);
        setError(null);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РіСЂСѓР·РёС‚СЊ event rules");
      });
  }, []);

  return (
    <section className="stack">
      <div className="toolbar">
        <div>
          <h2>Event Rules</h2>
          <p className="subtle">РќР°СЃС‚СЂР°РёРІР°Р№С‚Рµ РїРѕР»РЅС‹Р№ event-based РєРѕРЅС„РёРі РґР»СЏ РїР°СЂС‹ `db_backupper` + `s3_backupper`.</p>
        </div>
        <div className="toolbar-actions">
          <Link className="button primary" to="/event-rules/new">
            РќРѕРІРѕРµ РїСЂР°РІРёР»Рѕ
          </Link>
        </div>
      </div>

      {error ? <div className="alert">{error}</div> : null}

      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>РќР°Р·РІР°РЅРёРµ</th>
              <th>Namespace</th>
              <th>DB backup</th>
              <th>S3 backup</th>
              <th>Р’РєР»СЋС‡РµРЅРѕ</th>
              <th>Watcher</th>
              <th>РџРѕСЃР»РµРґРЅРёР№ combined run</th>
              <th>РћР±РЅРѕРІР»РµРЅРѕ</th>
            </tr>
          </thead>
          <tbody>
            {rules.map((rule) => (
              <tr key={rule.id}>
                <td>
                  <Link to={`/event-rules/${rule.id}`}>{rule.name}</Link>
                </td>
                <td>{rule.namespace}</td>
                <td>{rule.dbName}</td>
                <td>{rule.s3Name}</td>
                <td>{formatBoolean(rule.enabled)}</td>
                <td>{formatEventWatcherStatus(rule.eventWatcherStatus)}</td>
                <td>{formatDate(rule.lastTriggeredAt)}</td>
                <td>{formatDate(rule.updatedAt)}</td>
              </tr>
            ))}
            {rules.length === 0 ? (
              <tr>
                <td colSpan={8} className="empty-state">
                  Event rules РїРѕРєР° РЅРµ СЃРѕР·РґР°РЅС‹.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
