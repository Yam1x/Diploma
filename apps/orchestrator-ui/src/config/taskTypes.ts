export type TaskTypeDefinition = {
  routeType: string;
  serviceType: string;
  title: string;
  description: string;
  metadata: string;
};

export const taskTypes: TaskTypeDefinition[] = [
  {
    routeType: "db-backupper",
    serviceType: "db_backupper",
    title: "Резервное копирование БД",
    description:
      "Создаёт и деплоит задачу `db_backupper`, которая снимает дамп PostgreSQL и отправляет его в S3-совместимое хранилище.",
    metadata: "Подходит для регулярных backup-задач по cron-расписанию.",
  },
];

export function getTaskTypeByRouteType(routeType: string | undefined) {
  return taskTypes.find((taskType) => taskType.routeType === routeType) ?? null;
}

export function getTaskTypeByServiceType(serviceType: string) {
  return taskTypes.find((taskType) => taskType.serviceType === serviceType) ?? null;
}
