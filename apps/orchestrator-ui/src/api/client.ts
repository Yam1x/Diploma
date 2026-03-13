declare global {
  interface Window {
    __APP_CONFIG__?: {
      API_BASE_URL?: string;
    };
  }
}

const API_BASE_URL = window.__APP_CONFIG__?.API_BASE_URL ?? import.meta.env.VITE_API_BASE_URL ?? "/api";

export type TaskSummary = {
  id: number;
  name: string;
  namespace: string;
  enabled: boolean;
  serviceType: string;
  schedule: string;
  deployed: boolean;
  releaseName: string;
  lastApplyStatus: string | null;
  lastApplyMessage: string | null;
  lastAppliedAt: string | null;
  updatedAt: string;
};

export type TaskDetail = TaskSummary & {
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

export type TaskPayload = {
  name: string;
  namespace: string;
  enabled: boolean;
  schedule: string;
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
  updateTask: (taskId: string, payload: Partial<TaskPayload>) =>
    request<TaskDetail>(`/tasks/${taskId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  enableTask: (taskId: string) => request<TaskDetail>(`/tasks/${taskId}/enable`, { method: "POST" }),
  disableTask: (taskId: string) => request<TaskDetail>(`/tasks/${taskId}/disable`, { method: "POST" }),
  refreshTask: (taskId: string) => request<TaskDetail>(`/tasks/${taskId}/refresh`, { method: "POST" }),
  listNamespaces: () => request<{ namespaces: string[] }>("/namespaces"),
};
