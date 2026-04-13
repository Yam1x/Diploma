const API_BASE_URL = "/api";

export type ServiceType = "db_backupper" | "s3_backupper" | "env_synchronizer";
export type TriggerMode = "scheduled" | "event_based";

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

export type StorageStats = {
  bucketName: string;
  objectCount: number;
  totalSize: number;
};

export type JobRunSummary = {
  id: number;
  name: string;
  namespace: string;
  taskId: number;
  taskName: string;
  releaseName: string;
  triggerType: "manual" | "scheduled" | "event";
  status: "running" | "succeeded" | "failed" | "unknown";
  startedAt: string | null;
  completedAt: string | null;
  lastSeenAt: string | null;
  hasLogs: boolean;
};

export type TaskJobStats = {
  taskId: number;
  taskName: string;
  namespace: string;
  releaseName: string;
  totalRuns: number;
  manualRuns: number;
  scheduledRuns: number;
  eventRuns: number;
  succeededRuns: number;
  failedRuns: number;
  activeRuns: number;
  unknownRuns: number;
  lastStartedAt: string | null;
  lastCompletedAt: string | null;
};

export type JobsStats = {
  totalRuns: number;
  manualRuns: number;
  scheduledRuns: number;
  eventRuns: number;
  succeededRuns: number;
  failedRuns: number;
  activeRuns: number;
  unknownRuns: number;
  recentRuns: JobRunSummary[];
  tasks: TaskJobStats[];
};

export type DashboardStatsResponse = {
  storage: StorageStats;
  jobs: JobsStats;
};

export type TaskJobRunsResponse = {
  runs: JobRunSummary[];
};

export type JobRunLogsResponse = {
  run: JobRunSummary;
  logs: string;
};

export type NotificationItem = {
  id: number;
  kind: string;
  severity: "info" | "success" | "warning" | "error";
  title: string;
  message: string;
  taskId: number | null;
  jobRunId: number | null;
  linkPath: string | null;
  isRead: boolean;
  readAt: string | null;
  createdAt: string;
};

export type NotificationsResponse = {
  unreadCount: number;
  items: NotificationItem[];
};

type TaskSummaryBase = {
  id: number;
  name: string;
  namespace: string;
  enabled: boolean;
  serviceType: ServiceType;
  schedule: string | null;
  triggerMode: TriggerMode;
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

export type EnvSynchronizerTaskSummary = TaskSummaryBase & {
  serviceType: "env_synchronizer";
};

export type TaskSummary = DbTaskSummary | S3TaskSummary | EnvSynchronizerTaskSummary;

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
  eventWatcherStatus: string;
  lastEventDetectedAt: string | null;
  lastEventTriggeredAt: string | null;
  lastEventMessage: string | null;
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
  eventWatcherStatus: string;
  lastEventDetectedAt: string | null;
  lastEventTriggeredAt: string | null;
  lastEventMessage: string | null;
};

export type EnvSynchronizerTaskDetail = EnvSynchronizerTaskSummary & {
  envRepository: string;
  pathToHelmfile: string;
};

export type TaskDetail = DbTaskDetail | S3TaskDetail | EnvSynchronizerTaskDetail;

export type NamespacePayload = {
  name: string;
};

type TaskPayloadBase = {
  serviceType: ServiceType;
  name: string;
  namespace: string;
  enabled: boolean;
  schedule: string | null;
  triggerMode: TriggerMode;
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

export type EnvSynchronizerTaskPayload = TaskPayloadBase & {
  serviceType: "env_synchronizer";
  envRepository: string;
  pathToHelmfile: string;
};

export type TaskPayload = DbTaskPayload | S3TaskPayload | EnvSynchronizerTaskPayload;

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
  getDashboardStats: () => request<DashboardStatsResponse>("/stats/overview"),
  listNotifications: (limit = 20, unreadOnly = false) =>
    request<NotificationsResponse>(`/notifications?limit=${limit}&unreadOnly=${String(unreadOnly)}`),
  markNotificationRead: (notificationId: number) => request<void>(`/notifications/${notificationId}/read`, { method: "POST" }),
  markAllNotificationsRead: () => request<void>("/notifications/read-all", { method: "POST" }),
  listTasks: () => request<TaskSummary[]>("/tasks"),
  getTask: (taskId: string) => request<TaskDetail>(`/tasks/${taskId}`),
  listTaskJobRuns: (taskId: string) => request<TaskJobRunsResponse>(`/tasks/${taskId}/job-runs`),
  getTaskJobRunLogs: (taskId: string, runId: number) => request<JobRunLogsResponse>(`/tasks/${taskId}/job-runs/${runId}/logs`),
  createTask: (payload: TaskPayload) => request<TaskDetail>("/tasks", { method: "POST", body: JSON.stringify(payload) }),
  updateTask: (taskId: string, payload: TaskPayload) =>
    request<TaskDetail>(`/tasks/${taskId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  enableTask: (taskId: string) => request<TaskDetail>(`/tasks/${taskId}/enable`, { method: "POST" }),
  runTask: (taskId: string) => request<TaskDetail>(`/tasks/${taskId}/run`, { method: "POST" }),
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
  buildMinioObjectDownloadUrl: (key: string) => `${API_BASE_URL}/minio/objects/download?key=${encodeURIComponent(key)}`,
  deleteMinioObject: (key: string) => request<void>(`/minio/objects?key=${encodeURIComponent(key)}`, { method: "DELETE" }),
  createNamespace: (payload: NamespacePayload) => request<{ name: string }>("/namespaces", { method: "POST", body: JSON.stringify(payload) }),
};
