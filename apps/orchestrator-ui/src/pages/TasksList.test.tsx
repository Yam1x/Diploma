import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { vi } from "vitest";

import { TasksListPage } from "./TasksList";

vi.mock("../api/client", () => ({
  api: {
    listTasks: vi.fn().mockResolvedValue([
      {
        id: 1,
        name: "Primary DB",
        namespace: "default",
        enabled: true,
        deployed: true,
        serviceType: "db_backupper",
        schedule: "0 * * * *",
        releaseName: "db-backupper-primary-db",
        lastApplyStatus: "deployed",
        lastApplyMessage: "ok",
        lastAppliedAt: null,
        updatedAt: new Date().toISOString(),
      },
    ]),
    listNamespaces: vi.fn().mockResolvedValue({ namespaces: ["default"] }),
    refreshTask: vi.fn(),
    disableTask: vi.fn(),
    enableTask: vi.fn(),
  },
}));

test("renders task list", async () => {
  render(
    <BrowserRouter>
      <TasksListPage />
    </BrowserRouter>,
  );

  expect(await screen.findByText("Primary DB")).toBeInTheDocument();
});
