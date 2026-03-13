import { PropsWithChildren } from "react";
import { Link, useLocation } from "react-router-dom";

export function Layout({ children }: PropsWithChildren) {
  const location = useLocation();

  return (
    <div className="shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Diploma Control Plane</p>
          <h1>Оркестрация резервного копирования для Kubernetes</h1>
          <p className="subtle">
            Настраивайте состояние релиза, целевой namespace и параметры резервного копирования из одной панели.
          </p>
        </div>
        <nav className="nav">
          <Link className={location.pathname === "/" ? "nav-link active" : "nav-link"} to="/">
            Задачи
          </Link>
          <Link className={location.pathname === "/tasks/new" ? "nav-link active" : "nav-link"} to="/tasks/new">
            Новая задача
          </Link>
        </nav>
      </header>
      <main className="content">{children}</main>
    </div>
  );
}
