import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, test, vi } from "vitest";

const { api } = vi.hoisted(() => ({
  api: {
    listEventRules: vi.fn(),
    getEventRule: vi.fn(),
    listNamespaces: vi.fn(),
    listServiceDiscovery: vi.fn(),
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
      namespace: "default",
      enabled: true,
      dbName: "Primary DB",
      s3Name: "Bucket archive",
      eventWatcherStatus: "watching",
      lastTriggeredAt: null,
      updatedAt: new Date().toISOString(),
    },
  ]);
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
  api.getEventRule.mockResolvedValue({
    id: 1,
    name: "Combined backup",
    namespace: "default",
    enabled: true,
    dbName: "Primary DB",
    s3Name: "Bucket archive",
    eventWatcherStatus: "watching",
    lastTriggeredAt: null,
    updatedAt: new Date().toISOString(),
    lastPolledAt: null,
    lastDbChangeAt: null,
    lastS3ChangeAt: null,
    lastErrorAt: null,
    lastErrorMessage: null,
    db: {
      name: "Primary DB",
      dbBackupsFilenamePrefix: "primary",
      databaseHost: "postgresql",
      databaseName: "app",
      databaseUsername: "postgres",
      destinationAwsEndpoint: "http://minio:9000",
      destinationAwsBucketName: "backups",
      destinationAwsAccessKeyId: "minio",
      hasDatabasePassword: true,
      hasDestinationAwsSecretAccessKey: true,
    },
    s3: {
      name: "Bucket archive",
      s3BackupsFilenamePrefix: "bucket",
      sourceS3AwsEndpoint: "http://minio:9000",
      sourceS3AwsAccessKeyId: "minio",
      sourceS3AwsBucketName: "source",
      sourceS3AwsBucketSubfolderName: "incoming",
      destinationS3AwsEndpoint: "http://minio:9000",
      destinationS3AwsAccessKeyId: "minio",
      destinationS3AwsBucketName: "dest",
      hasSourceS3AwsSecretAccessKey: true,
      hasDestinationS3AwsSecretAccessKey: true,
    },
  });
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

test("renders event rule details", async () => {
  render(
    <MemoryRouter initialEntries={["/event-rules/1"]}>
      <Routes>
        <Route path="/event-rules/:ruleId" element={<EventRuleDetailsPage />} />
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByText("Combined backup")).toBeInTheDocument();
  expect(screen.getByText("DB backup config")).toBeInTheDocument();
  expect(screen.getByText("S3 backup config")).toBeInTheDocument();
});

test("renders event rule form", async () => {
  render(
    <MemoryRouter initialEntries={["/event-rules/new"]}>
      <Routes>
        <Route path="/event-rules/new" element={<EventRuleFormPage />} />
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByText("Создание event rule")).toBeInTheDocument();
  expect(screen.getByText("DB backup")).toBeInTheDocument();
  expect(screen.getByText("S3 backup")).toBeInTheDocument();
});
