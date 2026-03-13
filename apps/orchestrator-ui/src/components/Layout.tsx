import { PropsWithChildren } from "react";
import { Link, useLocation } from "react-router-dom";

export function Layout({ children }: PropsWithChildren) {
  const location = useLocation();
  const isTasks = location.pathname === "/";
  const isCreateFlow = location.pathname.startsWith("/tasks/new");

  return (
    <div className="app-frame">
      <div className="ambient ambient-left" />
      <div className="ambient ambient-right" />
      <div className="shell">
        <header className="hero-card">
          <div className="topbar">
            <div className="brand-mark">
              <span className="brand-dot" />
              <div>
                <p className="eyebrow">Diploma Orchestrator</p>
                <p className="topbar-note">Control Plane for Kubernetes</p>
              </div>
            </div>
            <nav className="nav">
              <Link className={isTasks ? "nav-link active" : "nav-link"} to="/">
                Задачи
              </Link>
              <Link className={isCreateFlow ? "nav-link active" : "nav-link"} to="/tasks/new">
                Новая задача
              </Link>
            </nav>
          </div>
          <div className="hero">
            <div className="hero-copy">
              <h1>Оркестрация резервного копирования в одном спокойном интерфейсе</h1>
              <p className="subtle hero-text">
                Управляйте namespace, параметрами бэкапа и состоянием релизов через лёгкую панель без лишнего визуального шума.
              </p>
            </div>
            <div className="hero-panel">
              <div className="hero-chip">Kubernetes</div>
              <div className="hero-chip">Helm</div>
              <div className="hero-chip">PostgreSQL</div>
              <div className="hero-chip">MinIO / S3</div>
            </div>
          </div>
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  );
}
