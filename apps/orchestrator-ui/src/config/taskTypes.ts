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
    description:
      "Создаёт и деплоит scheduled-задачу `db_backupper`, которая снимает дамп PostgreSQL и отправляет его в S3-совместимое хранилище.",
    metadata: "Подходит для backup-задач по расписанию. Event-based настройка перенесена в Event Rules.",
  },
  {
    routeType: "s3-backupper",
    serviceType: "s3_backupper",
    title: "Резервное копирование S3",
    description:
      "Создаёт и деплоит scheduled-задачу `s3_backupper`, которая архивирует содержимое одного S3 bucket и загружает архив в другой.",
    metadata: "Подходит для backup bucket-ов и subfolder-ов по расписанию. Event-based настройка перенесена в Event Rules.",
  },
  {
    routeType: "env-backupper",
    serviceType: "env_backupper",
    title: "Резервное копирование окружения",
    description:
      "Создаёт и деплоит scheduled-задачу `env_backupper`, которая снимает snapshot Kubernetes-ресурсов выбранного namespace и загружает архив в S3/MinIO.",
    metadata: "Подходит для плановых и ручных backup-ов инфраструктурного состояния namespace: сервисов, workload-ов, ConfigMap и Secret.",
  },
  {
    routeType: "env-restorer",
    serviceType: "env_restorer",
    title: "Р’РѕСЃСЃС‚Р°РЅРѕРІР»РµРЅРёРµ РѕРєСЂСѓР¶РµРЅРёСЏ",
    description:
      "РЎРѕР·РґР°С‘С‚ Рё РґРµРїР»РѕРёС‚ scheduled-Р·Р°РґР°С‡Сѓ `env_restorer`, РєРѕС‚РѕСЂР°СЏ РїСЂРё СЂСѓС‡РЅРѕРј Р·Р°РїСѓСЃРєРµ Р±РµСЂС‘С‚ РїРѕСЃР»РµРґРЅРёР№ snapshot-Р°СЂС…РёРІ namespace РёР· S3/MinIO Рё РїСЂРёРјРµРЅСЏРµС‚ РµРіРѕ РѕР±СЂР°С‚РЅРѕ РІ Kubernetes.",
    metadata: "РџРѕРґС…РѕРґРёС‚ РґР»СЏ СЂСѓС‡РЅРѕРіРѕ apply-only restore СЂРµСЃСѓСЂСЃРѕРІ namespace РёР· РїРѕСЃР»РµРґРЅРµРіРѕ backup-Р°СЂС…РёРІР° РїРѕ prefix.",
  },
  {
    routeType: "env-synchronizer",
    serviceType: "env_synchronizer",
    title: "Синхронизация окружения",
    description:
      "Создаёт и деплоит задачу `env_synchronizer`, которая клонирует репозиторий окружения и применяет Helmfile по расписанию.",
    metadata: "Подходит для регулярной синхронизации namespace с Git-репозиторием окружения.",
  },
];

export function getTaskTypeByRouteType(routeType: string | undefined) {
  return taskTypes.find((taskType) => taskType.routeType === routeType) ?? null;
}

export function getTaskTypeByServiceType(serviceType: ServiceType) {
  return taskTypes.find((taskType) => taskType.serviceType === serviceType) ?? null;
}
