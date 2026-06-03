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

test("renders env restore fields for env restore route", async () => {
  render(
    <MemoryRouter initialEntries={["/tasks/new/env-restorer"]}>
      <Routes>
        <Route path="/tasks/new/:taskType" element={<TaskFormPage />} />
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByText("Source S3 endpoint")).toBeInTheDocument();
  expect(screen.getByText("Source S3 bucket")).toBeInTheDocument();
});

test("renders db restore fields for db restore route", async () => {
  render(
    <MemoryRouter initialEntries={["/tasks/new/db-restorer"]}>
      <Routes>
        <Route path="/tasks/new/:taskType" element={<TaskFormPage />} />
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByText("Source S3 endpoint")).toBeInTheDocument();
  expect(screen.getByText("Хост целевой базы данных")).toBeInTheDocument();
});

test("renders s3 restore fields for s3 restore route", async () => {
  render(
    <MemoryRouter initialEntries={["/tasks/new/s3-restorer"]}>
      <Routes>
        <Route path="/tasks/new/:taskType" element={<TaskFormPage />} />
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByText("Target S3 endpoint")).toBeInTheDocument();
  expect(screen.getByText("Target S3 bucket")).toBeInTheDocument();
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

test("keeps existing env restore secret when edit form leaves it empty", async () => {
  const detail = {
    id: 8,
    name: "Namespace restore",
    namespace: "default",
    enabled: true,
    serviceType: "env_restorer",
    schedule: null,
    triggerMode: "manual",
    deployed: true,
    releaseName: "env-restorer-8",
    lastApplyStatus: "deployed",
    lastApplyMessage: "ok",
    lastAppliedAt: null,
    updatedAt: new Date().toISOString(),
    envBackupsFilenamePrefix: "namespace-default",
    destinationAwsEndpoint: "https://minio.local",
    destinationAwsBucketName: "backups",
    destinationAwsAccessKeyId: "minio",
    hasDestinationAwsSecretAccessKey: true,
  };

  api.getTask.mockResolvedValue(detail);
  api.updateTask.mockResolvedValue(detail);

  const user = userEvent.setup();

  render(
    <MemoryRouter initialEntries={["/tasks/8/edit"]}>
      <Routes>
        <Route path="/tasks/:taskId/edit" element={<TaskFormPage />} />
        <Route path="/tasks/:taskId" element={<div>details</div>} />
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByDisplayValue("backups")).toBeInTheDocument();

  const submitButton = document.querySelector('button[type="submit"]');
  expect(submitButton).not.toBeNull();
  await user.click(submitButton as HTMLButtonElement);

  await waitFor(() => expect(api.updateTask).toHaveBeenCalled());
  const payload = api.updateTask.mock.calls[0][1];

  expect(payload).not.toHaveProperty("destinationAwsSecretAccessKey");
});

test("keeps existing db restore secrets when edit form leaves them empty", async () => {
  const detail = {
    id: 9,
    name: "Primary DB restore",
    namespace: "default",
    enabled: true,
    serviceType: "db_restorer",
    schedule: null,
    triggerMode: "manual",
    deployed: true,
    releaseName: "db-restorer-9",
    lastApplyStatus: "deployed",
    lastApplyMessage: "ok",
    lastAppliedAt: null,
    updatedAt: new Date().toISOString(),
    dbBackupsFilenamePrefix: "primary",
    sourceAwsEndpoint: "https://minio.local",
    sourceAwsBucketName: "backups",
    sourceAwsAccessKeyId: "minio",
    targetDatabaseHost: "postgresql",
    targetDatabaseName: "app",
    targetDatabaseUsername: "postgres",
    hasSourceAwsSecretAccessKey: true,
    hasTargetDatabasePassword: true,
  };

  api.getTask.mockResolvedValue(detail);
  api.updateTask.mockResolvedValue(detail);

  const user = userEvent.setup();

  render(
    <MemoryRouter initialEntries={["/tasks/9/edit"]}>
      <Routes>
        <Route path="/tasks/:taskId/edit" element={<TaskFormPage />} />
        <Route path="/tasks/:taskId" element={<div>details</div>} />
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByDisplayValue("postgresql")).toBeInTheDocument();

  const submitButton = document.querySelector('button[type="submit"]');
  expect(submitButton).not.toBeNull();
  await user.click(submitButton as HTMLButtonElement);

  await waitFor(() => expect(api.updateTask).toHaveBeenCalled());
  const payload = api.updateTask.mock.calls[0][1];

  expect(payload).not.toHaveProperty("sourceAwsSecretAccessKey");
  expect(payload).not.toHaveProperty("targetDatabasePassword");
});

test("keeps existing s3 restore secrets when edit form leaves them empty", async () => {
  const detail = {
    id: 10,
    name: "Bucket restore",
    namespace: "default",
    enabled: true,
    serviceType: "s3_restorer",
    schedule: null,
    triggerMode: "manual",
    deployed: true,
    releaseName: "s3-restorer-10",
    lastApplyStatus: "deployed",
    lastApplyMessage: "ok",
    lastAppliedAt: null,
    updatedAt: new Date().toISOString(),
    s3BackupsFilenamePrefix: "bucket-archive",
    sourceS3AwsEndpoint: "https://source.local",
    sourceS3AwsBucketName: "source-bucket",
    sourceS3AwsAccessKeyId: "source-key",
    targetS3AwsEndpoint: "https://destination.local",
    targetS3AwsBucketName: "destination-bucket",
    targetS3AwsBucketSubfolderName: "restored",
    targetS3AwsAccessKeyId: "destination-key",
    hasSourceS3AwsSecretAccessKey: true,
    hasTargetS3AwsSecretAccessKey: true,
  };

  api.getTask.mockResolvedValue(detail);
  api.updateTask.mockResolvedValue(detail);

  const user = userEvent.setup();

  render(
    <MemoryRouter initialEntries={["/tasks/10/edit"]}>
      <Routes>
        <Route path="/tasks/:taskId/edit" element={<TaskFormPage />} />
        <Route path="/tasks/:taskId" element={<div>details</div>} />
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByDisplayValue("destination-bucket")).toBeInTheDocument();

  const submitButton = document.querySelector('button[type="submit"]');
  expect(submitButton).not.toBeNull();
  await user.click(submitButton as HTMLButtonElement);

  await waitFor(() => expect(api.updateTask).toHaveBeenCalled());
  const payload = api.updateTask.mock.calls[0][1];

  expect(payload).not.toHaveProperty("sourceS3AwsSecretAccessKey");
  expect(payload).not.toHaveProperty("targetS3AwsSecretAccessKey");
});

test("db backup task form does not offer event-based mode", async () => {
  render(
    <MemoryRouter initialEntries={["/tasks/new/db-backupper"]}>
      <Routes>
        <Route path="/tasks/new/:taskType" element={<TaskFormPage />} />
      </Routes>
    </MemoryRouter>,
  );

  await waitFor(() => expect(api.listNamespaces).toHaveBeenCalled());
  expect(screen.queryByRole("option", { name: /по событию/i })).not.toBeInTheDocument();
});
