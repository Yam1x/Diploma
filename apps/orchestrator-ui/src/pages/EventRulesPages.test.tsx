import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, test, vi } from "vitest";

const { api } = vi.hoisted(() => ({
  api: {
    listEventRules: vi.fn(),
    listTasks: vi.fn(),
    getEventRule: vi.fn(),
    createEventRule: vi.fn(),
    updateEventRule: vi.fn(),
    enableEventRule: vi.fn(),
    disableEventRule: vi.fn(),
    runEventRule: vi.fn(),
    deleteEventRule: vi.fn(),
  },
}));

vi.mock("../api/client", () => ({ api }));

import { EventRuleDetailsPage } from "./EventRuleDetails";
import { EventRuleFormPage } from "./EventRuleForm";
import { EventRulesListPage } from "./EventRulesList";

beforeEach(() => {
  vi.clearAllMocks();
  api.listEventRules.mockResolvedValue([
    {
      id: 1,
      name: "Combined backup",
      enabled: true,
      dbTaskId: 1,
      dbTaskName: "Primary DB",
      s3TaskId: 2,
      s3TaskName: "Bucket archive",
      eventWatcherStatus: "watching",
      lastTriggeredAt: null,
      updatedAt: new Date().toISOString(),
    },
  ]);
  api.listTasks.mockResolvedValue([
    {
      id: 1,
      name: "Primary DB",
      namespace: "default",
      enabled: true,
      deployed: true,
      serviceType: "db_backupper",
      schedule: null,
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
      enabled: true,
      deployed: true,
      serviceType: "s3_backupper",
      schedule: null,
      triggerMode: "event_based",
      releaseName: "s3-backupper-2",
      lastApplyStatus: "deployed",
      lastApplyMessage: "ok",
      lastAppliedAt: null,
      updatedAt: new Date().toISOString(),
    },
  ]);
  api.getEventRule.mockResolvedValue({
    id: 1,
    name: "Combined backup",
    enabled: true,
    dbTaskId: 1,
    dbTaskName: "Primary DB",
    s3TaskId: 2,
    s3TaskName: "Bucket archive",
    eventWatcherStatus: "watching",
    lastTriggeredAt: null,
    updatedAt: new Date().toISOString(),
    lastPolledAt: null,
    lastDbChangeAt: null,
    lastS3ChangeAt: null,
    lastErrorAt: null,
    lastErrorMessage: null,
  });
  api.createEventRule.mockResolvedValue({ id: 3 });
});

test("renders event rules list", async () => {
  render(
    <MemoryRouter initialEntries={["/event-rules"]}>
      <Routes>
        <Route path="/event-rules" element={<EventRulesListPage />} />
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByText("Combined backup")).toBeInTheDocument();
  expect(screen.getByText("Primary DB")).toBeInTheDocument();
  expect(screen.getByText("Bucket archive")).toBeInTheDocument();
});

test("event rule form can select db and s3 tasks", async () => {
  const user = userEvent.setup();

  render(
    <MemoryRouter initialEntries={["/event-rules/new"]}>
      <Routes>
        <Route path="/event-rules/new" element={<EventRuleFormPage />} />
        <Route path="/event-rules/:ruleId" element={<div>details</div>} />
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByText("DB task")).toBeInTheDocument();

  const selects = screen.getAllByRole("combobox");
  await user.selectOptions(selects[0], "1");
  await user.selectOptions(selects[1], "2");
  await user.click(screen.getByRole("button", { name: /event rule/i }));

  await waitFor(() => expect(api.createEventRule).toHaveBeenCalled());
  expect(api.createEventRule).toHaveBeenCalledWith(
    expect.objectContaining({
      dbTaskId: 1,
      s3TaskId: 2,
    }),
  );
});

test("renders event rule details", async () => {
  render(
    <MemoryRouter initialEntries={["/event-rules/1"]}>
      <Routes>
        <Route path="/event-rules/:ruleId" element={<EventRuleDetailsPage />} />
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByText("Combined backup")).toBeInTheDocument();
  expect(screen.getByText("Primary DB")).toBeInTheDocument();
  expect(screen.getByText("Bucket archive")).toBeInTheDocument();
});
