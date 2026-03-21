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
            </tr>
          </thead>
          <tbody>
            {objects.map((object) => (
              <tr key={object.key}>
                <td>{object.key}</td>
                <td>{formatSize(object.size)}</td>
                <td>{object.lastModified ? new Date(object.lastModified).toLocaleString() : "Неизвестно"}</td>
                <td>{object.etag ?? "-"}</td>
              </tr>
            ))}
            {objects.length === 0 ? (
              <tr>
                <td className="empty-state" colSpan={4}>
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
