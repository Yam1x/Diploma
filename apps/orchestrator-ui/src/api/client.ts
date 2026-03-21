const API_BASE_URL = "/api";

export type ServiceType = "db_backupper" | "s3_backupper";

export type ServiceDiscoveryPort = {
  name: string | null;
  port: number;
};

export type ServiceDiscoveryEndpoint = {
  label: string;
  value: string;
};

export type DiscoveredService = {
  name: string;
  host: string;
  ports: ServiceDiscoveryPort[];
  endpoints: ServiceDiscoveryEndpoint[];
};

export type ServiceDiscoveryResponse = {
  services: DiscoveredService[];
};

export type MinioObjectSummary = {
  key: string;
  size: number;
  lastModified: string | null;
  etag: string | null;
};

export type MinioObjectsResponse = {
  bucketName: string;
  prefix: string;
  objects: MinioObjectSummary[];
};

type TaskSummaryBase = {
  id: number;
  name: string;
  namespace: string;
  enabled: boolean;
  serviceType: ServiceType;
  schedule: string;
  deployed: boolean;
  releaseName: string;
  lastApplyStatus: string | null;
  lastApplyMessage: string | null;
  lastAppliedAt: string | null;
  updatedAt: string;
};

export type DbTaskSummary = TaskSummaryBase & {
  serviceType: "db_backupper";
};

export type S3TaskSummary = TaskSummaryBase & {
  serviceType: "s3_backupper";
};

export type TaskSummary = DbTaskSummary | S3TaskSummary;

export type DbTaskDetail = DbTaskSummary & {
  dbBackupsFilenamePrefix: string;
  databaseHost: string;
  databaseName: string;
  databaseUsername: string;
  destinationAwsEndpoint: string;
  destinationAwsBucketName: string;
  destinationAwsAccessKeyId: string;
  hasDatabasePassword: boolean;
  hasDestinationAwsSecretAccessKey: boolean;
};

export type S3TaskDetail = S3TaskSummary & {
  s3BackupsFilenamePrefix: string;
  sourceS3AwsEndpoint: string;
  sourceS3AwsAccessKeyId: string;
  sourceS3AwsBucketName: string;
  sourceS3AwsBucketSubfolderName: string;
  destinationS3AwsEndpoint: string;
  destinationS3AwsAccessKeyId: string;
  destinationS3AwsBucketName: string;
  hasSourceS3AwsSecretAccessKey: boolean;
  hasDestinationS3AwsSecretAccessKey: boolean;
};

export type TaskDetail = DbTaskDetail | S3TaskDetail;

export type NamespacePayload = {
  name: string;
};

type TaskPayloadBase = {
  serviceType: ServiceType;
  name: string;
  namespace: string;
  enabled: boolean;
  schedule: string;
};

export type DbTaskPayload = TaskPayloadBase & {
  serviceType: "db_backupper";
  dbBackupsFilenamePrefix: string;
  databaseHost: string;
  databaseName: string;
  databaseUsername: string;
  databasePassword?: string;
  destinationAwsEndpoint: string;
  destinationAwsBucketName: string;
  destinationAwsAccessKeyId: string;
  destinationAwsSecretAccessKey?: string;
};

export type S3TaskPayload = TaskPayloadBase & {
  serviceType: "s3_backupper";
  s3BackupsFilenamePrefix: string;
  sourceS3AwsEndpoint: string;
  sourceS3AwsAccessKeyId: string;
  sourceS3AwsBucketName: string;
  sourceS3AwsBucketSubfolderName: string;
  sourceS3AwsSecretAccessKey?: string;
  destinationS3AwsEndpoint: string;
  destinationS3AwsAccessKeyId: string;
  destinationS3AwsBucketName: string;
  destinationS3AwsSecretAccessKey?: string;
};

export type TaskPayload = DbTaskPayload | S3TaskPayload;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: "Ошибка запроса" }));
    throw new Error(payload.detail ?? "Ошибка запроса");
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export const api = {
  listTasks: () => request<TaskSummary[]>("/tasks"),
  getTask: (taskId: string) => request<TaskDetail>(`/tasks/${taskId}`),
  createTask: (payload: TaskPayload) => request<TaskDetail>("/tasks", { method: "POST", body: JSON.stringify(payload) }),
  updateTask: (taskId: string, payload: TaskPayload) =>
    request<TaskDetail>(`/tasks/${taskId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  enableTask: (taskId: string) => request<TaskDetail>(`/tasks/${taskId}/enable`, { method: "POST" }),
  disableTask: (taskId: string) => request<TaskDetail>(`/tasks/${taskId}/disable`, { method: "POST" }),
  refreshTask: (taskId: string) => request<TaskDetail>(`/tasks/${taskId}/refresh`, { method: "POST" }),
  deleteTask: (taskId: string) => request<void>(`/tasks/${taskId}`, { method: "DELETE" }),
  listNamespaces: () => request<{ namespaces: string[] }>("/namespaces"),
  listServiceDiscovery: (namespace: string) =>
    request<ServiceDiscoveryResponse>(`/namespaces/${encodeURIComponent(namespace)}/service-discovery`),
  listMinioObjects: (prefix = "") => {
    const query = prefix ? `?prefix=${encodeURIComponent(prefix)}` : "";
    return request<MinioObjectsResponse>(`/minio/objects${query}`);
  },
  createNamespace: (payload: NamespacePayload) => request<{ name: string }>("/namespaces", { method: "POST", body: JSON.stringify(payload) }),
};
