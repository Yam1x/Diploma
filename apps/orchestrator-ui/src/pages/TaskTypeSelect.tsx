import { Link } from "react-router-dom";

import { taskTypes } from "../config/taskTypes";

export function TaskTypeSelectPage() {
  return (
    <section className="stack">
      <div className="toolbar">
        <div>
          <h2>Выбор типа задачи</h2>
        </div>
        <Link className="button ghost" to="/">
          Назад
        </Link>
      </div>

      <div className="task-type-grid">
        {taskTypes.map((taskType) => (
          <article className="card task-type-card" key={taskType.routeType}>
            <div className="stack task-type-copy">
              <div>
                <h3>{taskType.title}</h3>
                {taskType.description ? <p className="subtle">{taskType.description}</p> : null}
              </div>
              {taskType.metadata ? <p className="field-help">{taskType.metadata}</p> : null}
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
