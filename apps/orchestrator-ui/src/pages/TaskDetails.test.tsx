import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, test, vi } from "vitest";

const { api } = vi.hoisted(() => ({
  api: {
    getTask: vi.fn(),
    listTaskJobRuns: vi.fn(),
    getTaskJobRunLogs: vi.fn(),
    refreshTask: vi.fn(),
    disableTask: vi.fn(),
    enableTask: vi.fn(),
    deleteTask: vi.fn(),
    runTask: vi.fn(),
  },
}));

vi.mock("../api/client", () => ({ api }));

import { TaskDetailsPage } from "./TaskDetails";

beforeEach(() => {
  vi.clearAllMocks();
  api.listTaskJobRuns.mockResolvedValue({ runs: [] });
});

test("renders s3-specific task details", async () => {
  api.getTask.mockResolvedValue({
    id: 3,
    name: "Bucket archive",
    namespace: "default",
    enabled: true,
    serviceType: "s3_backupper",
    schedule: "30 * * * *",
    triggerMode: "scheduled",
    deployed: true,
    releaseName: "s3-backupper-3",
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
  });

  render(
    <MemoryRouter initialEntries={["/tasks/3"]}>
      <Routes>
        <Route path="/tasks/:taskId" element={<TaskDetailsPage />} />
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByText("Bucket archive")).toBeInTheDocument();
  expect(screen.getByText("Source S3 bucket")).toBeInTheDocument();
  expect(screen.getByText("destination-bucket")).toBeInTheDocument();
});

test("renders event-based db watcher details", async () => {
  api.getTask.mockResolvedValue({
    id: 4,
    name: "Primary DB",
    namespace: "default",
    enabled: true,
    serviceType: "db_backupper",
    schedule: "0 * * * *",
    triggerMode: "event_based",
    deployed: true,
    releaseName: "db-backupper-4",
    lastApplyStatus: "deployed",
    lastApplyMessage: "ok",
    lastAppliedAt: null,
    updatedAt: new Date().toISOString(),
    dbBackupsFilenamePrefix: "primary",
    databaseHost: "postgresql",
    databaseName: "app",
    databaseUsername: "postgres",
    destinationAwsEndpoint: "http://minio:9000",
    destinationAwsBucketName: "backups",
    destinationAwsAccessKeyId: "minio",
    hasDatabasePassword: true,
    hasDestinationAwsSecretAccessKey: true,
    eventWatcherStatus: "watching",
    lastEventDetectedAt: new Date().toISOString(),
    lastEventTriggeredAt: new Date().toISOString(),
    lastEventMessage: null,
  });

  render(
    <MemoryRouter initialEntries={["/tasks/4"]}>
      <Routes>
        <Route path="/tasks/:taskId" element={<TaskDetailsPage />} />
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByText("Primary DB")).toBeInTheDocument();
  expect(screen.getByText("Event watcher")).toBeInTheDocument();
  expect(screen.getByText("По событию + cron fallback")).toBeInTheDocument();
});
