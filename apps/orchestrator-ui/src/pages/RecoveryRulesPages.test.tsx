import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, test, vi } from "vitest";

const { api } = vi.hoisted(() => ({
  api: {
    listRecoveryRules: vi.fn(),
    getRecoveryRule: vi.fn(),
    listNamespaces: vi.fn(),
    listServiceDiscovery: vi.fn(),
  },
}));

vi.mock("../api/client", () => ({ api }));

import { RecoveryRuleDetailsPage } from "./RecoveryRuleDetails";
import { RecoveryRuleFormPage } from "./RecoveryRuleForm";
import { RecoveryRulesListPage } from "./RecoveryRulesList";

beforeEach(() => {
  vi.clearAllMocks();
  api.listRecoveryRules.mockResolvedValue([
    {
      id: 1,
      name: "Combined recovery",
      namespace: "default",
      enabled: true,
      dbName: "Primary DB restore",
      s3Name: "Bucket restore",
      eventWatcherStatus: "watching",
      lastPolledAt: null,
      lastDbEmptyAt: null,
      lastS3EmptyAt: null,
      lastDbTriggeredAt: null,
      lastS3TriggeredAt: null,
      lastErrorAt: null,
      lastErrorMessage: null,
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
  api.getRecoveryRule.mockResolvedValue({
    id: 1,
    name: "Combined recovery",
    namespace: "default",
    enabled: true,
    dbName: "Primary DB restore",
    s3Name: "Bucket restore",
    eventWatcherStatus: "watching",
    lastDbTriggeredAt: null,
    lastS3TriggeredAt: null,
    updatedAt: new Date().toISOString(),
    lastPolledAt: null,
    lastDbEmptyAt: null,
    lastS3EmptyAt: null,
    lastErrorAt: null,
    lastErrorMessage: null,
    db: {
      name: "Primary DB restore",
      dbBackupsFilenamePrefix: "primary",
      sourceAwsEndpoint: "http://minio:9000",
      sourceAwsBucketName: "backups",
      sourceAwsAccessKeyId: "minio",
      targetDatabaseHost: "postgresql",
      targetDatabaseName: "app",
      targetDatabaseUsername: "postgres",
      hasSourceAwsSecretAccessKey: true,
      hasTargetDatabasePassword: true,
    },
    s3: {
      name: "Bucket restore",
      s3BackupsFilenamePrefix: "bucket",
      sourceS3AwsEndpoint: "http://minio:9000",
      sourceS3AwsBucketName: "source",
      sourceS3AwsAccessKeyId: "minio",
      targetS3AwsEndpoint: "http://minio:9000",
      targetS3AwsBucketName: "dest",
      targetS3AwsBucketSubfolderName: "incoming",
      targetS3AwsAccessKeyId: "minio",
      hasSourceS3AwsSecretAccessKey: true,
      hasTargetS3AwsSecretAccessKey: true,
    },
  });
});

test("renders recovery rules list", async () => {
  render(
    <MemoryRouter initialEntries={["/recovery-rules"]}>
      <Routes>
        <Route path="/recovery-rules" element={<RecoveryRulesListPage />} />
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByText("Combined recovery")).toBeInTheDocument();
  expect(screen.getByText("Primary DB restore")).toBeInTheDocument();
  expect(screen.getByText("Bucket restore")).toBeInTheDocument();
});

test("renders recovery rule details", async () => {
  render(
    <MemoryRouter initialEntries={["/recovery-rules/1"]}>
      <Routes>
        <Route path="/recovery-rules/:ruleId" element={<RecoveryRuleDetailsPage />} />
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByText("Combined recovery")).toBeInTheDocument();
  expect(screen.getByText("DB restore config")).toBeInTheDocument();
  expect(screen.getByText("S3 restore config")).toBeInTheDocument();
});

test("renders recovery rule form", async () => {
  render(
    <MemoryRouter initialEntries={["/recovery-rules/new"]}>
      <Routes>
        <Route path="/recovery-rules/new" element={<RecoveryRuleFormPage />} />
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByText("Создание recovery rule")).toBeInTheDocument();
  expect(screen.getByText("DB restore")).toBeInTheDocument();
  expect(screen.getByText("S3 restore")).toBeInTheDocument();
});
