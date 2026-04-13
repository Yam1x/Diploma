import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { beforeEach, vi } from "vitest";

const { api } = vi.hoisted(() => ({
  api: {
    listTasks: vi.fn(),
    listNamespaces: vi.fn(),
    getDashboardStats: vi.fn(),
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
      triggerMode: "event_based",
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
      triggerMode: "scheduled",
      releaseName: "s3-backupper-2",
      lastApplyStatus: null,
      lastApplyMessage: null,
      lastAppliedAt: null,
      updatedAt: new Date().toISOString(),
    },
  ]);
  api.listNamespaces.mockResolvedValue({ namespaces: ["default"] });
  api.getDashboardStats.mockResolvedValue({
    storage: { bucketName: "backups", objectCount: 2, totalSize: 1024 },
    jobs: {
      totalRuns: 3,
      manualRuns: 1,
      scheduledRuns: 1,
      eventRuns: 1,
      succeededRuns: 2,
      failedRuns: 0,
      activeRuns: 1,
      unknownRuns: 0,
      recentRuns: [],
      tasks: [],
    },
  });
});

test("renders task list with trigger modes", async () => {
  render(
    <BrowserRouter>
      <TasksListPage />
    </BrowserRouter>,
  );

  expect(await screen.findByText("Primary DB")).toBeInTheDocument();
  expect(screen.getByText("Bucket archive")).toBeInTheDocument();
  expect(screen.getByText("По событию")).toBeInTheDocument();
  expect(screen.getByText("По расписанию")).toBeInTheDocument();
});
