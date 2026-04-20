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
    title: "Р РµР·РµСЂРІРЅРѕРµ РєРѕРїРёСЂРѕРІР°РЅРёРµ Р‘Р”",
    description:
      "РЎРѕР·РґР°С‘С‚ Рё РґРµРїР»РѕРёС‚ scheduled-Р·Р°РґР°С‡Сѓ `db_backupper`, РєРѕС‚РѕСЂР°СЏ СЃРЅРёРјР°РµС‚ РґР°РјРї PostgreSQL Рё РѕС‚РїСЂР°РІР»СЏРµС‚ РµРіРѕ РІ S3-СЃРѕРІРјРµСЃС‚РёРјРѕРµ С…СЂР°РЅРёР»РёС‰Рµ.",
    metadata: "РџРѕРґС…РѕРґРёС‚ РґР»СЏ backup-Р·Р°РґР°С‡ РїРѕ СЂР°СЃРїРёСЃР°РЅРёСЋ. Event-based РЅР°СЃС‚СЂРѕР№РєР° РїРµСЂРµРЅРµСЃРµРЅР° РІ Event Rules.",
  },
  {
    routeType: "s3-backupper",
    serviceType: "s3_backupper",
    title: "Р РµР·РµСЂРІРЅРѕРµ РєРѕРїРёСЂРѕРІР°РЅРёРµ S3",
    description:
      "РЎРѕР·РґР°С‘С‚ Рё РґРµРїР»РѕРёС‚ scheduled-Р·Р°РґР°С‡Сѓ `s3_backupper`, РєРѕС‚РѕСЂР°СЏ Р°СЂС…РёРІРёСЂСѓРµС‚ СЃРѕРґРµСЂР¶РёРјРѕРµ РѕРґРЅРѕРіРѕ S3 bucket Рё Р·Р°РіСЂСѓР¶Р°РµС‚ Р°СЂС…РёРІ РІ РґСЂСѓРіРѕР№.",
    metadata: "РџРѕРґС…РѕРґРёС‚ РґР»СЏ backup bucket-РѕРІ Рё subfolder-РѕРІ РїРѕ СЂР°СЃРїРёСЃР°РЅРёСЋ. Event-based РЅР°СЃС‚СЂРѕР№РєР° РїРµСЂРµРЅРµСЃРµРЅР° РІ Event Rules.",
  },
  {
    routeType: "env-synchronizer",
    serviceType: "env_synchronizer",
    title: "РЎРёРЅС…СЂРѕРЅРёР·Р°С†РёСЏ РѕРєСЂСѓР¶РµРЅРёСЏ",
    description:
      "РЎРѕР·РґР°С‘С‚ Рё РґРµРїР»РѕРёС‚ Р·Р°РґР°С‡Сѓ `env_synchronizer`, РєРѕС‚РѕСЂР°СЏ РєР»РѕРЅРёСЂСѓРµС‚ СЂРµРїРѕР·РёС‚РѕСЂРёР№ РѕРєСЂСѓР¶РµРЅРёСЏ Рё РїСЂРёРјРµРЅСЏРµС‚ Helmfile РїРѕ СЂР°СЃРїРёСЃР°РЅРёСЋ.",
    metadata: "РџРѕРґС…РѕРґРёС‚ РґР»СЏ СЂРµРіСѓР»СЏСЂРЅРѕР№ СЃРёРЅС…СЂРѕРЅРёР·Р°С†РёРё namespace СЃ Git-СЂРµРїРѕР·РёС‚РѕСЂРёРµРј РѕРєСЂСѓР¶РµРЅРёСЏ.",
  },
];

export function getTaskTypeByRouteType(routeType: string | undefined) {
  return taskTypes.find((taskType) => taskType.routeType === routeType) ?? null;
}

export function getTaskTypeByServiceType(serviceType: ServiceType) {
  return taskTypes.find((taskType) => taskType.serviceType === serviceType) ?? null;
}
