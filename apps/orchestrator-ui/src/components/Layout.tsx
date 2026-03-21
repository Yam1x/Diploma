import { PropsWithChildren } from "react";
import { Link, useLocation } from "react-router-dom";

function isBackupSettingsRoute(pathname: string) {
  return pathname === "/" || (pathname.startsWith("/tasks/") && !pathname.startsWith("/tasks/new"));
}

export function Layout({ children }: PropsWithChildren) {
  const location = useLocation();

  return (
    <div className="shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Diploma Control Plane</p>
          <h1>Оркестрация резервного копирования для Kubernetes</h1>
          <p className="subtle">
            Настраивайте backup-сервисы и просматривайте артефакты в MinIO из одной панели управления.
          </p>
        </div>
      </header>
      <div className="workspace">
        <aside className="sidebar card">
          <div className="sidebar-group">
            <p className="sidebar-title">Сервисы бэкапирования</p>
            <nav className="sidebar-nav">
              <Link className={isBackupSettingsRoute(location.pathname) ? "sidebar-link active" : "sidebar-link"} to="/">
                Настройка сервисов
              </Link>
              <Link className={location.pathname.startsWith("/tasks/new") ? "sidebar-link active" : "sidebar-link"} to="/tasks/new">
                Новая задача
              </Link>
            </nav>
          </div>
          <div className="sidebar-group">
            <p className="sidebar-title">Хранилище</p>
            <nav className="sidebar-nav">
              <Link className={location.pathname.startsWith("/minio-files") ? "sidebar-link active" : "sidebar-link"} to="/minio-files">
                Просмотр файлов в MinIO
              </Link>
            </nav>
          </div>
        </aside>
        <main className="content">{children}</main>
      </div>
    </div>
  );
}
