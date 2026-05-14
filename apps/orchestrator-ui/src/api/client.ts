const API_BASE_URL = "/api";

export type ServiceType =
  | "db_backupper"
  | "s3_backupper"
  | "env_backupper"
  | "db_restorer"
  | "s3_restorer"
  | "env_restorer"
  | "env_synchronizer";
export type TriggerMode = "manual" | "scheduled" | "event_based";

export type EventRuleWatcherStatus = "disabled" | "waiting_for_baseline" | "watching" | "cooldown" | "error";
export type RecoveryRuleWatcherStatus =
  | "disabled"
  | "waiting_for_baseline"
  | "watching"
  | "restoring"
  | "cooldown"
  | "error";

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

export type EnvBackupperTaskSummary = TaskSummaryBase & {
  serviceType: "env_backupper";
};

export type DbRestorerTaskSummary = TaskSummaryBase & {
  serviceType: "db_restorer";
};

export type S3RestorerTaskSummary = TaskSummaryBase & {
  serviceType: "s3_restorer";
};

export type EnvRestorerTaskSummary = TaskSummaryBase & {
  serviceType: "env_restorer";
};

export type EnvSynchronizerTaskSummary = TaskSummaryBase & {
  serviceType: "env_synchronizer";
};

export type TaskSummary =
  | DbTaskSummary
  | S3TaskSummary
  | EnvBackupperTaskSummary
  | DbRestorerTaskSummary
  | S3RestorerTaskSummary
  | EnvRestorerTaskSummary
  | EnvSynchronizerTaskSummary;

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

export type EnvBackupperTaskDetail = EnvBackupperTaskSummary & {
  envBackupsFilenamePrefix: string;
  destinationAwsEndpoint: string;
  destinationAwsBucketName: string;
  destinationAwsAccessKeyId: string;
  hasDestinationAwsSecretAccessKey: boolean;
};

export type DbRestorerTaskDetail = DbRestorerTaskSummary & {
  dbBackupsFilenamePrefix: string;
  sourceAwsEndpoint: string;
  sourceAwsBucketName: string;
  sourceAwsAccessKeyId: string;
  targetDatabaseHost: string;
  targetDatabaseName: string;
  targetDatabaseUsername: string;
  hasSourceAwsSecretAccessKey: boolean;
  hasTargetDatabasePassword: boolean;
};

export type S3RestorerTaskDetail = S3RestorerTaskSummary & {
  s3BackupsFilenamePrefix: string;
  sourceS3AwsEndpoint: string;
  sourceS3AwsBucketName: string;
  sourceS3AwsAccessKeyId: string;
  targetS3AwsEndpoint: string;
  targetS3AwsBucketName: string;
  targetS3AwsBucketSubfolderName: string;
  targetS3AwsAccessKeyId: string;
  hasSourceS3AwsSecretAccessKey: boolean;
  hasTargetS3AwsSecretAccessKey: boolean;
};

export type EnvRestorerTaskDetail = EnvRestorerTaskSummary & {
  envBackupsFilenamePrefix: string;
  destinationAwsEndpoint: string;
  destinationAwsBucketName: string;
  destinationAwsAccessKeyId: string;
  hasDestinationAwsSecretAccessKey: boolean;
};

export type EnvSynchronizerTaskDetail = EnvSynchronizerTaskSummary & {
  envRepository: string;
  pathToHelmfile: string;
};

export type TaskDetail =
  | DbTaskDetail
  | S3TaskDetail
  | EnvBackupperTaskDetail
  | DbRestorerTaskDetail
  | S3RestorerTaskDetail
  | EnvRestorerTaskDetail
  | EnvSynchronizerTaskDetail;

export type BackupEventRuleSummary = {
  id: number;
  name: string;
  namespace: string;
  enabled: boolean;
  dbName: string;
  s3Name: string;
  eventWatcherStatus: EventRuleWatcherStatus | string;
  lastTriggeredAt: string | null;
  updatedAt: string;
};

export type BackupEventRuleDbDetail = {
  name: string;
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

export type BackupEventRuleS3Detail = {
  name: string;
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

export type BackupEventRuleDetail = BackupEventRuleSummary & {
  db: BackupEventRuleDbDetail;
  s3: BackupEventRuleS3Detail;
  lastPolledAt: string | null;
  lastDbChangeAt: string | null;
  lastS3ChangeAt: string | null;
  lastErrorAt: string | null;
  lastErrorMessage: string | null;
};

export type BackupEventRuleDbPayload = {
  name: string;
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

export type BackupEventRuleS3Payload = {
  name: string;
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

export type BackupEventRulePayload = {
  name: string;
  namespace: string;
  enabled: boolean;
  db: BackupEventRuleDbPayload;
  s3: BackupEventRuleS3Payload;
};

export type BackupEventRuleUpdatePayload = Partial<BackupEventRulePayload>;

export type RecoveryEventRuleSummary = {
  id: number;
  name: string;
  namespace: string;
  enabled: boolean;
  dbName: string;
  s3Name: string;
  eventWatcherStatus: RecoveryRuleWatcherStatus | string;
  lastPolledAt: string | null;
  lastDbEmptyAt: string | null;
  lastS3EmptyAt: string | null;
  lastDbTriggeredAt: string | null;
  lastS3TriggeredAt: string | null;
  lastErrorAt: string | null;
  lastErrorMessage: string | null;
  updatedAt: string;
};

export type RecoveryEventRuleDbDetail = {
  name: string;
  dbBackupsFilenamePrefix: string;
  sourceAwsEndpoint: string;
  sourceAwsBucketName: string;
  sourceAwsAccessKeyId: string;
  targetDatabaseHost: string;
  targetDatabaseName: string;
  targetDatabaseUsername: string;
  hasSourceAwsSecretAccessKey: boolean;
  hasTargetDatabasePassword: boolean;
};

export type RecoveryEventRuleS3Detail = {
  name: string;
  s3BackupsFilenamePrefix: string;
  sourceS3AwsEndpoint: string;
  sourceS3AwsBucketName: string;
  sourceS3AwsAccessKeyId: string;
  targetS3AwsEndpoint: string;
  targetS3AwsBucketName: string;
  targetS3AwsBucketSubfolderName: string;
  targetS3AwsAccessKeyId: string;
  hasSourceS3AwsSecretAccessKey: boolean;
  hasTargetS3AwsSecretAccessKey: boolean;
};

export type RecoveryEventRuleDetail = RecoveryEventRuleSummary & {
  db: RecoveryEventRuleDbDetail;
  s3: RecoveryEventRuleS3Detail;
};

export type RecoveryEventRuleDbPayload = {
  name: string;
  dbBackupsFilenamePrefix: string;
  sourceAwsEndpoint: string;
  sourceAwsBucketName: string;
  sourceAwsAccessKeyId: string;
  sourceAwsSecretAccessKey?: string;
  targetDatabaseHost: string;
  targetDatabaseName: string;
  targetDatabaseUsername: string;
  targetDatabasePassword?: string;
};

export type RecoveryEventRuleS3Payload = {
  name: string;
  s3BackupsFilenamePrefix: string;
  sourceS3AwsEndpoint: string;
  sourceS3AwsBucketName: string;
  sourceS3AwsAccessKeyId: string;
  sourceS3AwsSecretAccessKey?: string;
  targetS3AwsEndpoint: string;
  targetS3AwsBucketName: string;
  targetS3AwsBucketSubfolderName: string;
  targetS3AwsAccessKeyId: string;
  targetS3AwsSecretAccessKey?: string;
};

export type RecoveryEventRulePayload = {
  name: string;
  namespace: string;
  enabled: boolean;
  db: RecoveryEventRuleDbPayload;
  s3: RecoveryEventRuleS3Payload;
};

export type RecoveryEventRuleUpdatePayload = Partial<RecoveryEventRulePayload>;

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

export type EnvBackupperTaskPayload = TaskPayloadBase & {
  serviceType: "env_backupper";
  envBackupsFilenamePrefix: string;
  destinationAwsEndpoint: string;
  destinationAwsBucketName: string;
  destinationAwsAccessKeyId: string;
  destinationAwsSecretAccessKey?: string;
};

export type DbRestorerTaskPayload = TaskPayloadBase & {
  serviceType: "db_restorer";
  dbBackupsFilenamePrefix: string;
  sourceAwsEndpoint: string;
  sourceAwsBucketName: string;
  sourceAwsAccessKeyId: string;
  sourceAwsSecretAccessKey?: string;
  targetDatabaseHost: string;
  targetDatabaseName: string;
  targetDatabaseUsername: string;
  targetDatabasePassword?: string;
};

export type S3RestorerTaskPayload = TaskPayloadBase & {
  serviceType: "s3_restorer";
  s3BackupsFilenamePrefix: string;
  sourceS3AwsEndpoint: string;
  sourceS3AwsBucketName: string;
  sourceS3AwsAccessKeyId: string;
  sourceS3AwsSecretAccessKey?: string;
  targetS3AwsEndpoint: string;
  targetS3AwsBucketName: string;
  targetS3AwsBucketSubfolderName: string;
  targetS3AwsAccessKeyId: string;
  targetS3AwsSecretAccessKey?: string;
};

export type EnvRestorerTaskPayload = TaskPayloadBase & {
  serviceType: "env_restorer";
  envBackupsFilenamePrefix: string;
  destinationAwsEndpoint: string;
  destinationAwsBucketName: string;
  destinationAwsAccessKeyId: string;
  destinationAwsSecretAccessKey?: string;
};

export type EnvSynchronizerTaskPayload = TaskPayloadBase & {
  serviceType: "env_synchronizer";
  envRepository: string;
  pathToHelmfile: string;
};

export type TaskPayload =
  | DbTaskPayload
  | S3TaskPayload
  | EnvBackupperTaskPayload
  | DbRestorerTaskPayload
  | S3RestorerTaskPayload
  | EnvRestorerTaskPayload
  | EnvSynchronizerTaskPayload;

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

type BackendNotificationItem = {
  id: number;
  kind: string;
  severity: "info" | "success" | "warning" | "error";
  title: string;
  message: string;
  resourceType: string | null;
  resourceId: number | null;
  runType: string | null;
  runId: number | null;
  linkPath: string | null;
  isRead: boolean;
  readAt: string | null;
  createdAt: string;
};

type BackendTaskDetail = TaskSummaryBase & {
  config: Record<string, unknown>;
  watcher?: {
    status: string;
    lastDetectedAt: string | null;
    lastTriggeredAt: string | null;
    lastMessage: string | null;
  } | null;
};

type BackendRuleSummary = {
  id: number;
  name: string;
  namespace: string;
  enabled: boolean;
  dbConfig: { name: string };
  s3Config: { name: string };
  watcher: Record<string, string | null>;
  updatedAt: string;
};

type BackendRuleDetail = BackendRuleSummary & {
  dbConfig: Record<string, unknown>;
  s3Config: Record<string, unknown>;
};

function toTaskApiPayload(payload: TaskPayload) {
  const { serviceType, name, namespace, enabled, schedule, triggerMode, ...config } = payload;
  return { serviceType, name, namespace, enabled, schedule, triggerMode, config };
}

function fromTaskApiDetail(task: BackendTaskDetail): TaskDetail {
  if (task.serviceType === "db_backupper") {
    return {
      ...task,
      dbBackupsFilenamePrefix: String(task.config.dbBackupsFilenamePrefix ?? ""),
      databaseHost: String(task.config.databaseHost ?? ""),
      databaseName: String(task.config.databaseName ?? ""),
      databaseUsername: String(task.config.databaseUsername ?? ""),
      destinationAwsEndpoint: String(task.config.destinationAwsEndpoint ?? ""),
      destinationAwsBucketName: String(task.config.destinationAwsBucketName ?? ""),
      destinationAwsAccessKeyId: String(task.config.destinationAwsAccessKeyId ?? ""),
      hasDatabasePassword: Boolean(task.config.hasDatabasePassword),
      hasDestinationAwsSecretAccessKey: Boolean(task.config.hasDestinationAwsSecretAccessKey),
      eventWatcherStatus: task.watcher?.status ?? "scheduled",
      lastEventDetectedAt: task.watcher?.lastDetectedAt ?? null,
      lastEventTriggeredAt: task.watcher?.lastTriggeredAt ?? null,
      lastEventMessage: task.watcher?.lastMessage ?? null,
    } as DbTaskDetail;
  }
  if (task.serviceType === "s3_backupper") {
    return {
      ...task,
      s3BackupsFilenamePrefix: String(task.config.s3BackupsFilenamePrefix ?? ""),
      sourceS3AwsEndpoint: String(task.config.sourceS3AwsEndpoint ?? ""),
      sourceS3AwsAccessKeyId: String(task.config.sourceS3AwsAccessKeyId ?? ""),
      sourceS3AwsBucketName: String(task.config.sourceS3AwsBucketName ?? ""),
      sourceS3AwsBucketSubfolderName: String(task.config.sourceS3AwsBucketSubfolderName ?? ""),
      destinationS3AwsEndpoint: String(task.config.destinationS3AwsEndpoint ?? ""),
      destinationS3AwsAccessKeyId: String(task.config.destinationS3AwsAccessKeyId ?? ""),
      destinationS3AwsBucketName: String(task.config.destinationS3AwsBucketName ?? ""),
      hasSourceS3AwsSecretAccessKey: Boolean(task.config.hasSourceS3AwsSecretAccessKey),
      hasDestinationS3AwsSecretAccessKey: Boolean(task.config.hasDestinationS3AwsSecretAccessKey),
      eventWatcherStatus: task.watcher?.status ?? "scheduled",
      lastEventDetectedAt: task.watcher?.lastDetectedAt ?? null,
      lastEventTriggeredAt: task.watcher?.lastTriggeredAt ?? null,
      lastEventMessage: task.watcher?.lastMessage ?? null,
    } as S3TaskDetail;
  }
  if (task.serviceType === "env_backupper") {
    return {
      ...task,
      envBackupsFilenamePrefix: String(task.config.envBackupsFilenamePrefix ?? ""),
      destinationAwsEndpoint: String(task.config.destinationAwsEndpoint ?? ""),
      destinationAwsBucketName: String(task.config.destinationAwsBucketName ?? ""),
      destinationAwsAccessKeyId: String(task.config.destinationAwsAccessKeyId ?? ""),
      hasDestinationAwsSecretAccessKey: Boolean(task.config.hasDestinationAwsSecretAccessKey),
    } as EnvBackupperTaskDetail;
  }
  if (task.serviceType === "db_restorer") {
    return {
      ...task,
      dbBackupsFilenamePrefix: String(task.config.dbBackupsFilenamePrefix ?? ""),
      sourceAwsEndpoint: String(task.config.sourceAwsEndpoint ?? ""),
      sourceAwsBucketName: String(task.config.sourceAwsBucketName ?? ""),
      sourceAwsAccessKeyId: String(task.config.sourceAwsAccessKeyId ?? ""),
      targetDatabaseHost: String(task.config.targetDatabaseHost ?? ""),
      targetDatabaseName: String(task.config.targetDatabaseName ?? ""),
      targetDatabaseUsername: String(task.config.targetDatabaseUsername ?? ""),
      hasSourceAwsSecretAccessKey: Boolean(task.config.hasSourceAwsSecretAccessKey),
      hasTargetDatabasePassword: Boolean(task.config.hasTargetDatabasePassword),
    } as DbRestorerTaskDetail;
  }
  if (task.serviceType === "s3_restorer") {
    return {
      ...task,
      s3BackupsFilenamePrefix: String(task.config.s3BackupsFilenamePrefix ?? ""),
      sourceS3AwsEndpoint: String(task.config.sourceS3AwsEndpoint ?? ""),
      sourceS3AwsBucketName: String(task.config.sourceS3AwsBucketName ?? ""),
      sourceS3AwsAccessKeyId: String(task.config.sourceS3AwsAccessKeyId ?? ""),
      targetS3AwsEndpoint: String(task.config.targetS3AwsEndpoint ?? ""),
      targetS3AwsBucketName: String(task.config.targetS3AwsBucketName ?? ""),
      targetS3AwsBucketSubfolderName: String(task.config.targetS3AwsBucketSubfolderName ?? ""),
      targetS3AwsAccessKeyId: String(task.config.targetS3AwsAccessKeyId ?? ""),
      hasSourceS3AwsSecretAccessKey: Boolean(task.config.hasSourceS3AwsSecretAccessKey),
      hasTargetS3AwsSecretAccessKey: Boolean(task.config.hasTargetS3AwsSecretAccessKey),
    } as S3RestorerTaskDetail;
  }
  if (task.serviceType === "env_restorer") {
    return {
      ...task,
      envBackupsFilenamePrefix: String(task.config.envBackupsFilenamePrefix ?? ""),
      destinationAwsEndpoint: String(task.config.sourceAwsEndpoint ?? ""),
      destinationAwsBucketName: String(task.config.sourceAwsBucketName ?? ""),
      destinationAwsAccessKeyId: String(task.config.sourceAwsAccessKeyId ?? ""),
      hasDestinationAwsSecretAccessKey: Boolean(task.config.hasSourceAwsSecretAccessKey),
    } as EnvRestorerTaskDetail;
  }
  return {
    ...task,
    envRepository: String(task.config.envRepository ?? ""),
    pathToHelmfile: String(task.config.pathToHelmfile ?? ""),
  } as EnvSynchronizerTaskDetail;
}

function toEventRuleApiPayload(payload: BackupEventRulePayload | BackupEventRuleUpdatePayload) {
  const mapped: Record<string, unknown> = { ...payload };
  if ("db" in mapped) {
    mapped.dbConfig = mapped.db;
    delete mapped.db;
  }
  if ("s3" in mapped) {
    mapped.s3Config = mapped.s3;
    delete mapped.s3;
  }
  return mapped;
}

function fromEventRuleApi(rule: BackendRuleSummary | BackendRuleDetail): BackupEventRuleSummary | BackupEventRuleDetail {
  const base = {
    id: rule.id,
    name: rule.name,
    namespace: rule.namespace,
    enabled: rule.enabled,
    dbName: rule.dbConfig.name,
    s3Name: rule.s3Config.name,
    eventWatcherStatus: String(rule.watcher.status ?? "disabled"),
    updatedAt: rule.updatedAt,
  };
  if (!("dbBackupsFilenamePrefix" in rule.dbConfig)) {
    return { ...base, lastTriggeredAt: rule.watcher.lastTriggeredAt ?? null } as BackupEventRuleSummary;
  }
  return {
    ...base,
    lastTriggeredAt: (rule.watcher.lastTriggeredAt as string | null) ?? null,
    db: rule.dbConfig as BackupEventRuleDbDetail,
    s3: rule.s3Config as BackupEventRuleS3Detail,
    lastPolledAt: (rule.watcher.lastPolledAt as string | null) ?? null,
    lastDbChangeAt: (rule.watcher.lastDbChangeAt as string | null) ?? null,
    lastS3ChangeAt: (rule.watcher.lastS3ChangeAt as string | null) ?? null,
    lastErrorAt: (rule.watcher.lastErrorAt as string | null) ?? null,
    lastErrorMessage: (rule.watcher.lastErrorMessage as string | null) ?? null,
  } as BackupEventRuleDetail;
}

function toRecoveryRuleApiPayload(payload: RecoveryEventRulePayload | RecoveryEventRuleUpdatePayload) {
  const mapped: Record<string, unknown> = { ...payload };
  if ("db" in mapped) {
    mapped.dbConfig = mapped.db;
    delete mapped.db;
  }
  if ("s3" in mapped) {
    mapped.s3Config = mapped.s3;
    delete mapped.s3;
  }
  return mapped;
}

function fromRecoveryRuleApi(rule: BackendRuleSummary | BackendRuleDetail): RecoveryEventRuleSummary | RecoveryEventRuleDetail {
  const base = {
    id: rule.id,
    name: rule.name,
    namespace: rule.namespace,
    enabled: rule.enabled,
    dbName: rule.dbConfig.name,
    s3Name: rule.s3Config.name,
    eventWatcherStatus: String(rule.watcher.status ?? "disabled"),
    lastPolledAt: (rule.watcher.lastPolledAt as string | null) ?? null,
    lastDbEmptyAt: (rule.watcher.lastDbEmptyAt as string | null) ?? null,
    lastS3EmptyAt: (rule.watcher.lastS3EmptyAt as string | null) ?? null,
    lastDbTriggeredAt: (rule.watcher.lastDbTriggeredAt as string | null) ?? null,
    lastS3TriggeredAt: (rule.watcher.lastS3TriggeredAt as string | null) ?? null,
    lastErrorAt: (rule.watcher.lastErrorAt as string | null) ?? null,
    lastErrorMessage: (rule.watcher.lastErrorMessage as string | null) ?? null,
    updatedAt: rule.updatedAt,
  };
  if (!("dbBackupsFilenamePrefix" in rule.dbConfig)) {
    return base as RecoveryEventRuleSummary;
  }
  return { ...base, db: rule.dbConfig as RecoveryEventRuleDbDetail, s3: rule.s3Config as RecoveryEventRuleS3Detail } as RecoveryEventRuleDetail;
}

function fromNotificationApi(item: BackendNotificationItem): NotificationItem {
  return {
    id: item.id,
    kind: item.kind,
    severity: item.severity,
    title: item.title,
    message: item.message,
    taskId: item.resourceType === "task" ? item.resourceId : null,
    jobRunId: item.runType === "task_job_run" ? item.runId : null,
    linkPath: item.linkPath,
    isRead: item.isRead,
    readAt: item.readAt,
    createdAt: item.createdAt,
  };
}

export const api = {
  getDashboardStats: () => request<DashboardStatsResponse>("/stats/overview"),
  listNotifications: (limit = 20, unreadOnly = false) =>
    request<{ unreadCount: number; items: BackendNotificationItem[] }>(`/notifications?limit=${limit}&unreadOnly=${String(unreadOnly)}`).then((response) => ({
      unreadCount: response.unreadCount,
      items: response.items.map(fromNotificationApi),
    })),
  markNotificationRead: (notificationId: number) => request<void>(`/notifications/${notificationId}/read`, { method: "POST" }),
  markAllNotificationsRead: () => request<void>("/notifications/read-all", { method: "POST" }),
  listTasks: () => request<TaskSummary[]>("/tasks"),
  getTask: (taskId: string) => request<BackendTaskDetail>(`/tasks/${taskId}`).then(fromTaskApiDetail),
  listEventRules: () => request<BackendRuleSummary[]>("/event-rules").then((items) => items.map((item) => fromEventRuleApi(item) as BackupEventRuleSummary)),
  getEventRule: (ruleId: string) => request<BackendRuleDetail>(`/event-rules/${ruleId}`).then((item) => fromEventRuleApi(item) as BackupEventRuleDetail),
  createEventRule: (payload: BackupEventRulePayload) =>
    request<BackendRuleDetail>("/event-rules", { method: "POST", body: JSON.stringify(toEventRuleApiPayload(payload)) }).then(
      (item) => fromEventRuleApi(item) as BackupEventRuleDetail,
    ),
  updateEventRule: (ruleId: string, payload: BackupEventRuleUpdatePayload) =>
    request<BackendRuleDetail>(`/event-rules/${ruleId}`, { method: "PATCH", body: JSON.stringify(toEventRuleApiPayload(payload)) }).then(
      (item) => fromEventRuleApi(item) as BackupEventRuleDetail,
    ),
  enableEventRule: (ruleId: string) => request<BackendRuleDetail>(`/event-rules/${ruleId}/enable`, { method: "POST" }).then((item) => fromEventRuleApi(item) as BackupEventRuleDetail),
  runEventRule: (ruleId: string) => request<BackendRuleDetail>(`/event-rules/${ruleId}/run`, { method: "POST" }).then((item) => fromEventRuleApi(item) as BackupEventRuleDetail),
  disableEventRule: (ruleId: string) => request<BackendRuleDetail>(`/event-rules/${ruleId}/disable`, { method: "POST" }).then((item) => fromEventRuleApi(item) as BackupEventRuleDetail),
  deleteEventRule: (ruleId: string) => request<void>(`/event-rules/${ruleId}`, { method: "DELETE" }),
  listRecoveryRules: () =>
    request<BackendRuleSummary[]>("/recovery-rules").then((items) => items.map((item) => fromRecoveryRuleApi(item) as RecoveryEventRuleSummary)),
  getRecoveryRule: (ruleId: string) =>
    request<BackendRuleDetail>(`/recovery-rules/${ruleId}`).then((item) => fromRecoveryRuleApi(item) as RecoveryEventRuleDetail),
  createRecoveryRule: (payload: RecoveryEventRulePayload) =>
    request<BackendRuleDetail>("/recovery-rules", { method: "POST", body: JSON.stringify(toRecoveryRuleApiPayload(payload)) }).then(
      (item) => fromRecoveryRuleApi(item) as RecoveryEventRuleDetail,
    ),
  updateRecoveryRule: (ruleId: string, payload: RecoveryEventRuleUpdatePayload) =>
    request<BackendRuleDetail>(`/recovery-rules/${ruleId}`, { method: "PATCH", body: JSON.stringify(toRecoveryRuleApiPayload(payload)) }).then(
      (item) => fromRecoveryRuleApi(item) as RecoveryEventRuleDetail,
    ),
  enableRecoveryRule: (ruleId: string) => request<BackendRuleDetail>(`/recovery-rules/${ruleId}/enable`, { method: "POST" }).then((item) => fromRecoveryRuleApi(item) as RecoveryEventRuleDetail),
  runRecoveryRule: (ruleId: string) => request<BackendRuleDetail>(`/recovery-rules/${ruleId}/run`, { method: "POST" }).then((item) => fromRecoveryRuleApi(item) as RecoveryEventRuleDetail),
  runRecoveryRuleDb: (ruleId: string) => request<BackendRuleDetail>(`/recovery-rules/${ruleId}/run/db`, { method: "POST" }).then((item) => fromRecoveryRuleApi(item) as RecoveryEventRuleDetail),
  runRecoveryRuleS3: (ruleId: string) => request<BackendRuleDetail>(`/recovery-rules/${ruleId}/run/s3`, { method: "POST" }).then((item) => fromRecoveryRuleApi(item) as RecoveryEventRuleDetail),
  disableRecoveryRule: (ruleId: string) => request<BackendRuleDetail>(`/recovery-rules/${ruleId}/disable`, { method: "POST" }).then((item) => fromRecoveryRuleApi(item) as RecoveryEventRuleDetail),
  deleteRecoveryRule: (ruleId: string) => request<void>(`/recovery-rules/${ruleId}`, { method: "DELETE" }),
  listTaskJobRuns: (taskId: string) => request<TaskJobRunsResponse>(`/tasks/${taskId}/job-runs`),
  getTaskJobRunLogs: (taskId: string, runId: number) => request<JobRunLogsResponse>(`/tasks/${taskId}/job-runs/${runId}/logs`),
  createTask: (payload: TaskPayload) =>
    request<BackendTaskDetail>("/tasks", { method: "POST", body: JSON.stringify(toTaskApiPayload(payload)) }).then(fromTaskApiDetail),
  updateTask: (taskId: string, payload: TaskPayload) =>
    request<BackendTaskDetail>(`/tasks/${taskId}`, { method: "PATCH", body: JSON.stringify(toTaskApiPayload(payload)) }).then(fromTaskApiDetail),
  enableTask: (taskId: string) => request<BackendTaskDetail>(`/tasks/${taskId}/enable`, { method: "POST" }).then(fromTaskApiDetail),
  runTask: (taskId: string) => request<BackendTaskDetail>(`/tasks/${taskId}/run`, { method: "POST" }).then(fromTaskApiDetail),
  disableTask: (taskId: string) => request<BackendTaskDetail>(`/tasks/${taskId}/disable`, { method: "POST" }).then(fromTaskApiDetail),
  refreshTask: (taskId: string) => request<BackendTaskDetail>(`/tasks/${taskId}/refresh`, { method: "POST" }).then(fromTaskApiDetail),
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
