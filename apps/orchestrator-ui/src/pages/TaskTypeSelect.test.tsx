import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";

import { TaskTypeSelectPage } from "./TaskTypeSelect";

test("renders both supported task types", () => {
  render(
    <BrowserRouter>
      <TaskTypeSelectPage />
    </BrowserRouter>,
  );

  expect(screen.getByText("Резервное копирование БД")).toBeInTheDocument();
  expect(screen.getByText("Резервное копирование S3")).toBeInTheDocument();
});
