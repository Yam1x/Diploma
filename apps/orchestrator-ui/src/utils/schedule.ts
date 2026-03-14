export type ScheduleMode = "hourly" | "daily" | "weekly" | "monthly" | "custom";

export type ScheduleDraft = {
  mode: ScheduleMode;
  minute: string;
  time: string;
  weekday: string;
  monthDay: string;
  custom: string;
};

export const defaultScheduleDraft: ScheduleDraft = {
  mode: "daily",
  minute: "0",
  time: "00:00",
  weekday: "1",
  monthDay: "1",
  custom: "",
};

function parseNumber(value: string, min: number, max: number): number | null {
  if (!/^\d+$/.test(value)) {
    return null;
  }

  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < min || parsed > max) {
    return null;
  }

  return parsed;
}

function formatTime(hour: number, minute: number): string {
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

function parseTime(value: string): { hour: number; minute: number } {
  const [hourPart = "0", minutePart = "0"] = value.split(":");

  return {
    hour: parseNumber(hourPart, 0, 23) ?? 0,
    minute: parseNumber(minutePart, 0, 59) ?? 0,
  };
}

export function buildSchedule(draft: ScheduleDraft): string {
  if (draft.mode === "custom") {
    return draft.custom.trim();
  }

  if (draft.mode === "hourly") {
    const minute = parseNumber(draft.minute, 0, 59) ?? 0;
    return `${minute} * * * *`;
  }

  const { hour, minute } = parseTime(draft.time);

  if (draft.mode === "daily") {
    return `${minute} ${hour} * * *`;
  }

  if (draft.mode === "weekly") {
    const weekday = parseNumber(draft.weekday, 0, 6) ?? 1;
    return `${minute} ${hour} * * ${weekday}`;
  }

  const monthDay = parseNumber(draft.monthDay, 1, 31) ?? 1;
  return `${minute} ${hour} ${monthDay} * *`;
}

export function parseSchedule(schedule: string): ScheduleDraft {
  const trimmed = schedule.trim();
  if (!trimmed) {
    return { ...defaultScheduleDraft };
  }

  const parts = trimmed.split(/\s+/);
  if (parts.length !== 5) {
    return { ...defaultScheduleDraft, mode: "custom", custom: trimmed };
  }

  const [minutePart, hourPart, dayOfMonthPart, monthPart, dayOfWeekPart] = parts;
  const minute = parseNumber(minutePart, 0, 59);
  const hour = parseNumber(hourPart, 0, 23);
  const dayOfMonth = parseNumber(dayOfMonthPart, 1, 31);
  const dayOfWeek = parseNumber(dayOfWeekPart, 0, 6);

  if (minute !== null && hourPart === "*" && dayOfMonthPart === "*" && monthPart === "*" && dayOfWeekPart === "*") {
    return {
      ...defaultScheduleDraft,
      mode: "hourly",
      minute: String(minute),
      custom: trimmed,
    };
  }

  if (minute !== null && hour !== null && dayOfMonthPart === "*" && monthPart === "*" && dayOfWeekPart === "*") {
    return {
      ...defaultScheduleDraft,
      mode: "daily",
      time: formatTime(hour, minute),
      custom: trimmed,
    };
  }

  if (minute !== null && hour !== null && dayOfMonthPart === "*" && monthPart === "*" && dayOfWeek !== null) {
    return {
      ...defaultScheduleDraft,
      mode: "weekly",
      time: formatTime(hour, minute),
      weekday: String(dayOfWeek),
      custom: trimmed,
    };
  }

  if (minute !== null && hour !== null && dayOfMonth !== null && monthPart === "*" && dayOfWeekPart === "*") {
    return {
      ...defaultScheduleDraft,
      mode: "monthly",
      time: formatTime(hour, minute),
      monthDay: String(dayOfMonth),
      custom: trimmed,
    };
  }

  return { ...defaultScheduleDraft, mode: "custom", custom: trimmed };
}
