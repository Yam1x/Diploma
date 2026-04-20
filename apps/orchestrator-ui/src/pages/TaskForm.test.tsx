import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, test, vi } from "vitest";

const { api } = vi.hoisted(() => ({
  api: {
    listNamespaces: vi.fn(),
    listServiceDiscovery: vi.fn(),
    getTask: vi.fn(),
    createTask: vi.fn(),
    updateTask: vi.fn(),
    createNamespace: vi.fn(),
  },
}));

vi.mock("../api/client", () => ({ api }));

import { TaskFormPage } from "./TaskForm";

beforeEach(() => {
  vi.clearAllMocks();
  api.listNamespaces.mockResolvedValue({ namespaces: ["default"] });
  api.listServiceDiscovery.mockResolvedValue({
    services: [
      {
        name: "postgresql",
        host: "postgresql",
        ports: [{ name: "postgresql", port: 5432 }],
        endpoints: [{ label: "postgresql:5432 (postgresql)", value: "http://postgresql:5432" }],
      },
      {
        name: "minio",
        host: "minio",
        ports: [{ name: "api", port: 9000 }],
        endpoints: [{ label: "minio:9000 (api)", value: "http://minio:9000" }],
      },
    ],
  });
  api.createNamespace.mockResolvedValue({ name: "default" });
});

test("renders s3 fields for s3 task route", async () => {
  render(
    <MemoryRouter initialEntries={["/tasks/new/s3-backupper"]}>
      <Routes>
        <Route path="/tasks/new/:taskType" element={<TaskFormPage />} />
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByText("Source S3 endpoint")).toBeInTheDocument();
  expect(screen.getByText("Destination S3 bucket")).toBeInTheDocument();
});

test("fills database host from service discovery", async () => {
  const user = userEvent.setup();

  render(
    <MemoryRouter initialEntries={["/tasks/new/db-backupper"]}>
      <Routes>
        <Route path="/tasks/new/:taskType" element={<TaskFormPage />} />
      </Routes>
    </MemoryRouter>,
  );

  await waitFor(() => expect(api.listNamespaces).toHaveBeenCalled());
  await user.selectOptions(screen.getAllByRole("combobox")[1], "default");

  await waitFor(() => expect(api.listServiceDiscovery).toHaveBeenCalledWith("default"));
  await user.selectOptions(screen.getAllByRole("combobox")[3], "postgresql");

  expect(screen.getByDisplayValue("postgresql")).toBeInTheDocument();
});

test("fills source s3 endpoint from service discovery", async () => {
  const user = userEvent.setup();

  render(
    <MemoryRouter initialEntries={["/tasks/new/s3-backupper"]}>
      <Routes>
        <Route path="/tasks/new/:taskType" element={<TaskFormPage />} />
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByText("Source S3 endpoint")).toBeInTheDocument();

  await user.selectOptions(screen.getAllByRole("combobox")[0], "default");
  await waitFor(() => expect(api.listServiceDiscovery).toHaveBeenCalledWith("default"));
  await user.selectOptions(screen.getAllByRole("combobox")[2], "http://minio:9000");

  expect(screen.getByDisplayValue("http://minio:9000")).toBeInTheDocument();
});

test("keeps existing s3 secrets when edit form leaves them empty", async () => {
  const detail = {
    id: 7,
    name: "Bucket archive",
    namespace: "default",
    enabled: true,
    serviceType: "s3_backupper",
    schedule: "30 * * * *",
    triggerMode: "scheduled",
    deployed: true,
    releaseName: "s3-backupper-7",
    lastApplyStatus: "deployed",
    lastApplyMessage: "ok",
    lastAppliedAt: null,
    updatedAt: new Date().toISOString(),
    s3BackupsFilenamePrefix: "bucket-archive",
    sourceS3AwsEndpoint: "https://source.local",
    sourceS3AwsAccessKeyId: "source-key",
    sourceS3AwsBucketName: "source-bucket",
    sourceS3AwsBucketSubfolderName: "incoming",
    destinationS3AwsEndpoint: "https://destination.local",
    destinationS3AwsAccessKeyId: "destination-key",
    destinationS3AwsBucketName: "destination-bucket",
    hasSourceS3AwsSecretAccessKey: true,
    hasDestinationS3AwsSecretAccessKey: true,
  };

  api.getTask.mockResolvedValue(detail);
  api.updateTask.mockResolvedValue(detail);

  const user = userEvent.setup();

  render(
    <MemoryRouter initialEntries={["/tasks/7/edit"]}>
      <Routes>
        <Route path="/tasks/:taskId/edit" element={<TaskFormPage />} />
        <Route path="/tasks/:taskId" element={<div>details</div>} />
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByDisplayValue("source-bucket")).toBeInTheDocument();
  await waitFor(() => expect(api.listServiceDiscovery).toHaveBeenCalledWith("default"));

  const submitButton = document.querySelector('button[type="submit"]');
  expect(submitButton).not.toBeNull();
  await user.click(submitButton as HTMLButtonElement);

  await waitFor(() => expect(api.updateTask).toHaveBeenCalled());
  const payload = api.updateTask.mock.calls[0][1];

  expect(payload).not.toHaveProperty("sourceS3AwsSecretAccessKey");
  expect(payload).not.toHaveProperty("destinationS3AwsSecretAccessKey");
});

test("allows switching db backup task to event-based mode", async () => {
  const user = userEvent.setup();

  render(
    <MemoryRouter initialEntries={["/tasks/new/db-backupper"]}>
      <Routes>
        <Route path="/tasks/new/:taskType" element={<TaskFormPage />} />
      </Routes>
    </MemoryRouter>,
  );

  await waitFor(() => expect(api.listNamespaces).toHaveBeenCalled());
  await user.selectOptions(screen.getAllByRole("combobox")[0], "event_based");

  expect(screen.getByText(/Event Rules/i)).toBeInTheDocument();
});
