import type { ServiceType } from "../api/client";

export type TaskTypeDefinition = {
  routeType: string;
  serviceType: ServiceType;
  title: string;
  description: string;
  metadata: string;
};

export const taskTypes: TaskTypeDefinition[] = [
  {
    routeType: "db-backupper",
    serviceType: "db_backupper",
    title: "Резервное копирование БД",
    description: "Дамп PostgreSQL в S3.",
    metadata: "",
  },
  {
    routeType: "s3-backupper",
    serviceType: "s3_backupper",
    title: "Резервное копирование S3",
    description: "Архив S3 bucket.",
    metadata: "",
  },
  {
    routeType: "env-backupper",
    serviceType: "env_backupper",
    title: "Резервное копирование окружения",
    description: "Архив ресурсов namespace.",
    metadata: "",
  },
  {
    routeType: "db-restorer",
    serviceType: "db_restorer",
    title: "Восстановление БД",
    description: "Восстановление БД из backup.",
    metadata: "",
  },
  {
    routeType: "s3-restorer",
    serviceType: "s3_restorer",
    title: "Восстановление S3",
    description: "Восстановление S3 из backup.",
    metadata: "",
  },
  {
    routeType: "env-restorer",
    serviceType: "env_restorer",
    title: "Восстановление окружения",
    description: "Восстановление namespace из backup.",
    metadata: "",
  },
  {
    routeType: "env-synchronizer",
    serviceType: "env_synchronizer",
    title: "Синхронизация окружения",
    description: "Синхронизация окружения с Git.",
    metadata: "",
  },
];

export function getTaskTypeByRouteType(routeType: string | undefined) {
  return taskTypes.find((taskType) => taskType.routeType === routeType) ?? null;
}

export function getTaskTypeByServiceType(serviceType: ServiceType) {
  return taskTypes.find((taskType) => taskType.serviceType === serviceType) ?? null;
}
