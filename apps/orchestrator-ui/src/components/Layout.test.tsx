import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { test } from "vitest";

import { Layout } from "./Layout";

test("renders sidebar with backup and minio sections", () => {
  render(
    <MemoryRouter initialEntries={["/minio-files"]}>
      <Layout>
        <div>content</div>
      </Layout>
    </MemoryRouter>,
  );

  expect(screen.getByText("Сервисы бэкапирования")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Настройка сервисов" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Просмотр файлов в MinIO" })).toHaveClass("active");
});
