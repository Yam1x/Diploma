import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, vi } from "vitest";

const { api } = vi.hoisted(() => ({
  api: {
    getTask: vi.fn(),
    refreshTask: vi.fn(),
    disableTask: vi.fn(),
    enableTask: vi.fn(),
    deleteTask: vi.fn(),
  },
}));

vi.mock("../api/client", () => ({ api }));

import { TaskDetailsPage } from "./TaskDetails";

beforeEach(() => {
  vi.clearAllMocks();
});

test("renders s3-specific task details", async () => {
  api.getTask.mockResolvedValue({
    id: 3,
    name: "Bucket archive",
    namespace: "default",
    enabled: true,
    serviceType: "s3_backupper",
    schedule: "30 * * * *",
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

  expect(await screen.findByText("Резервное копирование S3")).toBeInTheDocument();
  expect(screen.getByText("Source S3 bucket")).toBeInTheDocument();
  expect(screen.getByText("destination-bucket")).toBeInTheDocument();
});
