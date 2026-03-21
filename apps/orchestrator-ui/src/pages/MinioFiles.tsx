import { FormEvent, useEffect, useState } from "react";

import { MinioObjectSummary, api } from "../api/client";

function formatSize(size: number) {
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KiB`;
  }
  if (size < 1024 * 1024 * 1024) {
    return `${(size / (1024 * 1024)).toFixed(1)} MiB`;
  }
  return `${(size / (1024 * 1024 * 1024)).toFixed(1)} GiB`;
}

export function MinioFilesPage() {
  const [bucketName, setBucketName] = useState("");
  const [prefix, setPrefix] = useState("");
  const [appliedPrefix, setAppliedPrefix] = useState("");
  const [objects, setObjects] = useState<MinioObjectSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load(nextPrefix = appliedPrefix) {
    try {
      setLoading(true);
      const response = await api.listMinioObjects(nextPrefix);
      setBucketName(response.bucketName);
      setAppliedPrefix(response.prefix);
      setObjects(response.objects);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить файлы MinIO");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load("");
  }, []);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void load(prefix);
  }

  async function handleDelete(key: string) {
    if (!window.confirm(`Удалить файл \"${key}\"?`)) {
      return;
    }

    try {
      setBusyKey(key);
      await api.deleteMinioObject(key);
      await load(appliedPrefix);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось удалить файл MinIO");
    } finally {
      setBusyKey(null);
    }
  }

  return (
    <section className="stack">
      <div className="toolbar">
        <div>
          <h2>Файлы MinIO</h2>
          <p className="subtle">
            Просматривайте содержимое bucket `{bucketName || "..."}` и фильтруйте список по префиксу каталога.
          </p>
        </div>
      </div>

      <form className="card filter-bar" onSubmit={handleSubmit}>
        <label>
          <span>Префикс</span>
          <small className="field-help">Например: `db/`, `s3/`, `archive/2026/`.</small>
          <input value={prefix} onChange={(event) => setPrefix(event.target.value)} placeholder="archive/" />
        </label>
        <div className="toolbar-actions">
          <button className="button primary" type="submit" disabled={loading}>
            {loading ? "Загрузка..." : "Применить"}
          </button>
          <button
            className="button ghost"
            type="button"
            onClick={() => {
              setPrefix("");
              void load("");
            }}
            disabled={loading}
          >
            Сбросить
          </button>
        </div>
      </form>

      {error ? <div className="alert">{error}</div> : null}

      <div className="card table-wrap">
        <div className="toolbar">
          <div>
            <h3>Содержимое bucket</h3>
            <p className="subtle">Текущий префикс: `{appliedPrefix || "/"}`</p>
          </div>
        </div>
        <table>
          <thead>
            <tr>
              <th>Ключ</th>
              <th>Размер</th>
              <th>Изменён</th>
              <th>ETag</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {objects.map((object) => {
              const isBusy = busyKey === object.key;

              return (
                <tr key={object.key}>
                  <td>{object.key}</td>
                  <td>{formatSize(object.size)}</td>
                  <td>{object.lastModified ? new Date(object.lastModified).toLocaleString() : "Неизвестно"}</td>
                  <td>{object.etag ?? "-"}</td>
                  <td className="row-actions">
                    <a className="button ghost" href={api.buildMinioObjectDownloadUrl(object.key)}>
                      Скачать
                    </a>
                    <button className="button danger" type="button" disabled={isBusy} onClick={() => void handleDelete(object.key)}>
                      {isBusy ? "Удаляем..." : "Удалить"}
                    </button>
                  </td>
                </tr>
              );
            })}
            {objects.length === 0 ? (
              <tr>
                <td className="empty-state" colSpan={5}>
                  {loading ? "Загружаем список файлов..." : "Файлы по выбранному префиксу не найдены."}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
