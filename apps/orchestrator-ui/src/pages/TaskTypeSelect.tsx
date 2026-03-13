import { Link } from "react-router-dom";

import { taskTypes } from "../config/taskTypes";

export function TaskTypeSelectPage() {
  return (
    <section className="stack">
      <div className="toolbar">
        <div>
          <h2>Выбор типа задачи</h2>
          <p className="subtle">Сначала выберите, какой сервис нужно создать, и только затем переходите к его настройке.</p>
        </div>
        <Link className="button ghost" to="/">
          Назад
        </Link>
      </div>

      <div className="form-intro card">
        <div>
          <p className="eyebrow">Service Catalog</p>
          <h3>Выберите тип управляемого сервиса</h3>
          <p className="subtle">Сейчас доступно резервное копирование базы данных, но интерфейс уже готов к расширению под новые сервисы.</p>
        </div>
      </div>

      <div className="task-type-grid">
        {taskTypes.map((taskType) => (
          <article className="card task-type-card" key={taskType.routeType}>
            <div className="stack task-type-copy">
              <div>
                <h3>{taskType.title}</h3>
                <p className="subtle">{taskType.description}</p>
              </div>
              <p className="field-help">{taskType.metadata}</p>
            </div>
            <Link className="button primary" to={`/tasks/new/${taskType.routeType}`}>
              Выбрать
            </Link>
          </article>
        ))}
      </div>
    </section>
  );
}
