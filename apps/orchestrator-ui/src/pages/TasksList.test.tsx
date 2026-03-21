import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { beforeEach, vi } from "vitest";

const { api } = vi.hoisted(() => ({
  api: {
    listTasks: vi.fn(),
    listNamespaces: vi.fn(),
    refreshTask: vi.fn(),
    disableTask: vi.fn(),
    enableTask: vi.fn(),
    deleteTask: vi.fn(),
    createNamespace: vi.fn(),
  },
}));

vi.mock("../api/client", () => ({ api }));

import { TasksListPage } from "./TasksList";

beforeEach(() => {
  vi.clearAllMocks();
  api.listTasks.mockResolvedValue([
    {
      id: 1,
      name: "Primary DB",
      namespace: "default",
      enabled: true,
      deployed: true,
      serviceType: "db_backupper",
      schedule: "0 * * * *",
      releaseName: "db-backupper-1",
      lastApplyStatus: "deployed",
      lastApplyMessage: "ok",
      lastAppliedAt: null,
      updatedAt: new Date().toISOString(),
    },
    {
      id: 2,
      name: "Bucket archive",
      namespace: "default",
      enabled: false,
      deployed: false,
      serviceType: "s3_backupper",
      schedule: "30 * * * *",
      releaseName: "s3-backupper-2",
      lastApplyStatus: null,
      lastApplyMessage: null,
      lastAppliedAt: null,
      updatedAt: new Date().toISOString(),
    },
  ]);
  api.listNamespaces.mockResolvedValue({ namespaces: ["default"] });
});

test("renders task list with both service types", async () => {
  render(
    <BrowserRouter>
      <TasksListPage />
    </BrowserRouter>,
  );

  expect(await screen.findByText("Primary DB")).toBeInTheDocument();
  expect(screen.getByText("Bucket archive")).toBeInTheDocument();
  expect(screen.getByText("Резервное копирование БД")).toBeInTheDocument();
  expect(screen.getByText("Резервное копирование S3")).toBeInTheDocument();
});
