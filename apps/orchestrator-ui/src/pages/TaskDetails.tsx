import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { JobRunSummary, TaskDetail, api } from "../api/client";
import { useNotifications } from "../components/NotificationsProvider";
import { getTaskTypeByServiceType } from "../config/taskTypes";

function formatBoolean(value: boolean) {
  return value ? "Р”Р°" : "РќРµС‚";
}

function formatApplyStatus(status: string | null) {
  const labels: Record<string, string> = {
    deployed: "РџСЂРёРјРµРЅРµРЅРѕ",
    failed: "РћС€РёР±РєР°",
    disabled: "РћС‚РєР»СЋС‡РµРЅРѕ",
    missing: "РќРµ РЅР°Р№РґРµРЅРѕ",
  };

  if (!status) {
    return "РћР¶РёРґР°РЅРёРµ";
  }

  return labels[status] ?? status;
}

function formatServiceType(serviceType: TaskDetail["serviceType"]) {
  return getTaskTypeByServiceType(serviceType)?.title ?? serviceType;
}

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString() : "РќРёРєРѕРіРґР°";
}

function formatTriggerType(triggerType: JobRunSummary["triggerType"]) {
  if (triggerType === "manual") {
    return "Р’СЂСѓС‡РЅСѓСЋ";
  }
  if (triggerType === "event") {
    return "РџРѕ СЃРѕР±С‹С‚РёСЋ";
  }
  return "РџРѕ СЂР°СЃРїРёСЃР°РЅРёСЋ";
}

function formatTriggerMode(triggerMode: TaskDetail["triggerMode"]) {
  return triggerMode === "event_based" ? "РџРѕ СЃРѕР±С‹С‚РёСЋ" : "РџРѕ СЂР°СЃРїРёСЃР°РЅРёСЋ";
}

function formatJobStatus(status: JobRunSummary["status"]) {
  const labels: Record<JobRunSummary["status"], string> = {
    running: "Р’С‹РїРѕР»РЅСЏРµС‚СЃСЏ",
    succeeded: "РЈСЃРїРµС€РЅРѕ",
    failed: "РћС€РёР±РєР°",
    unknown: "РќРµРёР·РІРµСЃС‚РЅРѕ",
  };

  return labels[status];
}

function renderTaskParameters(task: TaskDetail) {
  if (task.serviceType === "db_backupper") {
    return (
      <article className="card">
        <h3>РџР°СЂР°РјРµС‚СЂС‹ РІС‹РїРѕР»РЅРµРЅРёСЏ</h3>
        <dl>
          <dt>РҐРѕСЃС‚ Р±Р°Р·С‹ РґР°РЅРЅС‹С…</dt>
          <dd>{task.databaseHost}</dd>
          <dt>РРјСЏ Р±Р°Р·С‹ РґР°РЅРЅС‹С…</dt>
          <dd>{task.databaseName}</dd>
          <dt>РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ Р±Р°Р·С‹ РґР°РЅРЅС‹С…</dt>
          <dd>{task.databaseUsername}</dd>
          <dt>S3 endpoint</dt>
          <dd>{task.destinationAwsEndpoint}</dd>
          <dt>S3 bucket</dt>
          <dd>{task.destinationAwsBucketName}</dd>
        </dl>
      </article>
    );
  }

  if (task.serviceType === "s3_backupper") {
    return (
      <article className="card">
        <h3>РџР°СЂР°РјРµС‚СЂС‹ РІС‹РїРѕР»РЅРµРЅРёСЏ</h3>
        <dl>
          <dt>Source S3 endpoint</dt>
          <dd>{task.sourceS3AwsEndpoint}</dd>
          <dt>Source S3 bucket</dt>
          <dd>{task.sourceS3AwsBucketName}</dd>
          <dt>Source S3 subfolder</dt>
          <dd>{task.sourceS3AwsBucketSubfolderName || "Р’РµСЃСЊ bucket"}</dd>
          <dt>Destination S3 endpoint</dt>
          <dd>{task.destinationS3AwsEndpoint}</dd>
          <dt>Destination S3 bucket</dt>
          <dd>{task.destinationS3AwsBucketName}</dd>
        </dl>
      </article>
    );
  }

  return (
    <article className="card">
      <h3>РџР°СЂР°РјРµС‚СЂС‹ РІС‹РїРѕР»РЅРµРЅРёСЏ</h3>
      <dl>
        <dt>Р РµРїРѕР·РёС‚РѕСЂРёР№ РѕРєСЂСѓР¶РµРЅРёСЏ</dt>
        <dd>{task.envRepository}</dd>
        <dt>РџСѓС‚СЊ Рє Helmfile</dt>
        <dd>{task.pathToHelmfile}</dd>
      </dl>
    </article>
  );
}

export function TaskDetailsPage() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const { refreshNotifications } = useNotifications();
  const [task, setTask] = useState<TaskDetail | null>(null);
  const [jobRuns, setJobRuns] = useState<JobRunSummary[]>([]);
  const [selectedRun, setSelectedRun] = useState<JobRunSummary | null>(null);
  const [selectedRunLogs, setSelectedRunLogs] = useState("");
  const [logsLoading, setLogsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [logsError, setLogsError] = useState<string | null>(null);

  async function load() {
    if (!taskId) {
      return;
    }
    try {
      const [detail, runsResponse] = await Promise.all([api.getTask(taskId), api.listTaskJobRuns(taskId)]);
      setTask(detail);
      setJobRuns(runsResponse.runs);
      setSelectedRun((current) => (current ? runsResponse.runs.find((run) => run.id === current.id) ?? null : null));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РіСЂСѓР·РёС‚СЊ Р·Р°РґР°С‡Сѓ");
    }
  }

  useEffect(() => {
    void load();
  }, [taskId]);

  async function run(action: () => Promise<TaskDetail>) {
    try {
      await action();
      await load();
      await refreshNotifications();
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "РќРµ СѓРґР°Р»РѕСЃСЊ РІС‹РїРѕР»РЅРёС‚СЊ РґРµР№СЃС‚РІРёРµ");
    }
  }

  async function handleDelete() {
    if (!task) {
      return;
    }
    if (!window.confirm(`РЈРґР°Р»РёС‚СЊ Р·Р°РґР°С‡Сѓ "${task.name}"?`)) {
      return;
    }
    try {
      await api.deleteTask(String(task.id));
      setError(null);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "РќРµ СѓРґР°Р»РѕСЃСЊ СѓРґР°Р»РёС‚СЊ Р·Р°РґР°С‡Сѓ");
    }
  }

  async function handleLoadLogs(runItem: JobRunSummary) {
    if (!taskId) {
      return;
    }
    try {
      setSelectedRun(runItem);
      setLogsError(null);
      setLogsLoading(true);
      const response = await api.getTaskJobRunLogs(taskId, runItem.id);
      setSelectedRun(response.run);
      setSelectedRunLogs(response.logs);
    } catch (err) {
      setSelectedRun(runItem);
      setSelectedRunLogs("");
      setLogsError(err instanceof Error ? err.message : "РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РіСЂСѓР·РёС‚СЊ Р»РѕРіРё Р·Р°РїСѓСЃРєР°");
    } finally {
      setLogsLoading(false);
    }
  }

  if (!task) {
    return <section className="stack">{error ? <div className="alert">{error}</div> : <p>Р—Р°РіСЂСѓР·РєР°...</p>}</section>;
  }

  return (
    <section className="stack">
      <div className="toolbar">
        <div>
          <h2>{task.name}</h2>
          <p className="subtle">РўРµРєСѓС‰РёР№ СЂРµР»РёР·: `{task.releaseName}` РІ namespace `{task.namespace}`.</p>
        </div>
        <div className="toolbar-actions">
          <Link className="button ghost" to={`/tasks/${task.id}/edit`}>
            РР·РјРµРЅРёС‚СЊ
          </Link>
          <button className="button ghost" onClick={() => void run(() => api.refreshTask(String(task.id)))}>
            РћР±РЅРѕРІРёС‚СЊ
          </button>
          <button className="button primary" onClick={() => void run(() => api.runTask(String(task.id)))} disabled={!task.enabled}>
            Р—Р°РїСѓСЃС‚РёС‚СЊ СЃРµР№С‡Р°СЃ
          </button>
          {task.enabled ? (
            <button className="button danger" onClick={() => void run(() => api.disableTask(String(task.id)))}>
              Р’С‹РєР»СЋС‡РёС‚СЊ
            </button>
          ) : (
            <button className="button primary" onClick={() => void run(() => api.enableTask(String(task.id)))}>
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
          <h3>Р–РµР»Р°РµРјРѕРµ СЃРѕСЃС‚РѕСЏРЅРёРµ</h3>
          <dl>
            <dt>Р’РєР»СЋС‡РµРЅР°</dt>
            <dd>{formatBoolean(task.enabled)}</dd>
            <dt>РўРёРї СЃРµСЂРІРёСЃР°</dt>
            <dd>{formatServiceType(task.serviceType)}</dd>
            <dt>Р РµР¶РёРј Р·Р°РїСѓСЃРєР°</dt>
            <dd>{formatTriggerMode(task.triggerMode)}</dd>
            <dt>Р Р°СЃРїРёСЃР°РЅРёРµ</dt>
            <dd>{task.schedule ?? "РќРµ РёСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ"}</dd>
            {task.serviceType === "db_backupper" ? (
              <>
                <dt>РџСЂРµС„РёРєСЃ РёРјРµРЅРё С„Р°Р№Р»Р°</dt>
                <dd>{task.dbBackupsFilenamePrefix}</dd>
              </>
            ) : task.serviceType === "s3_backupper" ? (
              <>
                <dt>РџСЂРµС„РёРєСЃ РёРјРµРЅРё Р°СЂС…РёРІР°</dt>
                <dd>{task.s3BackupsFilenamePrefix}</dd>
              </>
            ) : null}
          </dl>
        </article>
        <article className="card">
          <h3>РЎРѕСЃС‚РѕСЏРЅРёРµ РґРµРїР»РѕСЏ</h3>
          <dl>
            <dt>Р—Р°РґРµРїР»РѕРµРЅР°</dt>
            <dd>{formatBoolean(task.deployed)}</dd>
            <dt>РЎС‚Р°С‚СѓСЃ РїРѕСЃР»РµРґРЅРµРіРѕ РїСЂРёРјРµРЅРµРЅРёСЏ</dt>
            <dd>{formatApplyStatus(task.lastApplyStatus)}</dd>
            <dt>РџРѕСЃР»РµРґРЅРµРµ РїСЂРёРјРµРЅРµРЅРёРµ</dt>
            <dd>{task.lastAppliedAt ? new Date(task.lastAppliedAt).toLocaleString() : "РќРёРєРѕРіРґР°"}</dd>
            <dt>РџРѕСЃР»РµРґРЅРµРµ СЃРѕРѕР±С‰РµРЅРёРµ</dt>
            <dd>{task.lastApplyMessage ?? "РЎРѕРѕР±С‰РµРЅРёР№ РїРѕРєР° РЅРµС‚"}</dd>
          </dl>
        </article>
        {renderTaskParameters(task)}
      </div>

      <article className="card table-wrap">
        <div className="toolbar">
          <div>
            <h3>РџРѕСЃР»РµРґРЅРёРµ Р·Р°РїСѓСЃРєРё</h3>
            <p className="subtle">РЎРїРёСЃРѕРє РїРѕСЃР»РµРґРЅРёС… `Job` СЌС‚РѕР№ Р·Р°РґР°С‡Рё СЃ РґРѕСЃС‚СѓРїРѕРј Рє РёС… Р»РѕРіР°Рј.</p>
          </div>
        </div>
        <table>
          <thead>
            <tr>
              <th>Job</th>
              <th>Р—Р°РїСѓСЃРє</th>
              <th>РЎС‚Р°С‚СѓСЃ</th>
              <th>РЎС‚Р°СЂС‚</th>
              <th>Р—Р°РІРµСЂС€РµРЅРёРµ</th>
              <th>РџРѕСЃР»РµРґРЅРёР№ sync</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {jobRuns.map((runItem) => (
              <tr key={runItem.id}>
                <td>{runItem.name}</td>
                <td>{formatTriggerType(runItem.triggerType)}</td>
                <td>{formatJobStatus(runItem.status)}</td>
                <td>{formatDate(runItem.startedAt)}</td>
                <td>{formatDate(runItem.completedAt)}</td>
                <td>{formatDate(runItem.lastSeenAt)}</td>
                <td className="row-actions">
                  <button className="button ghost" onClick={() => void handleLoadLogs(runItem)} disabled={logsLoading && selectedRun?.id === runItem.id}>
                    {logsLoading && selectedRun?.id === runItem.id ? "Р—Р°РіСЂСѓР¶Р°РµРј..." : runItem.hasLogs ? "Р›РѕРіРё" : "РџРѕР»СѓС‡РёС‚СЊ Р»РѕРіРё"}
                  </button>
                </td>
              </tr>
            ))}
            {jobRuns.length === 0 ? (
              <tr>
                <td colSpan={7} className="empty-state">
                  Р—Р°РїСѓСЃРєРё `Job` РґР»СЏ СЌС‚РѕР№ Р·Р°РґР°С‡Рё РїРѕРєР° РЅРµ РЅР°Р№РґРµРЅС‹.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </article>

      {selectedRun ? (
        <article className="card">
          <div className="toolbar">
            <div>
              <h3>Р›РѕРіРё Р·Р°РїСѓСЃРєР°</h3>
              <p className="subtle">
                `{selectedRun.name}` В· {formatJobStatus(selectedRun.status)} В· {formatDate(selectedRun.startedAt)}
              </p>
            </div>
          </div>
          {logsError ? <div className="alert">{logsError}</div> : null}
          <pre className="log-output">{selectedRunLogs || (logsLoading ? "Р—Р°РіСЂСѓР¶Р°РµРј Р»РѕРіРё..." : "Р›РѕРіРё РґР»СЏ СЌС‚РѕРіРѕ Р·Р°РїСѓСЃРєР° РїРѕРєР° РЅРµРґРѕСЃС‚СѓРїРЅС‹.")}</pre>
        </article>
      ) : null}
    </section>
  );
}
