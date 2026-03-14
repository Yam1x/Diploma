import { buildSchedule, defaultScheduleDraft, parseSchedule } from "./schedule";

describe("schedule utils", () => {
  it("builds hourly schedules", () => {
    expect(buildSchedule({ ...defaultScheduleDraft, mode: "hourly", minute: "15" })).toBe("15 * * * *");
  });

  it("builds daily schedules", () => {
    expect(buildSchedule({ ...defaultScheduleDraft, mode: "daily", time: "03:45" })).toBe("45 3 * * *");
  });

  it("parses supported presets", () => {
    expect(parseSchedule("0 * * * *")).toMatchObject({ mode: "hourly", minute: "0" });
    expect(parseSchedule("30 6 * * *")).toMatchObject({ mode: "daily", time: "06:30" });
    expect(parseSchedule("5 9 * * 1")).toMatchObject({ mode: "weekly", time: "09:05", weekday: "1" });
    expect(parseSchedule("10 2 15 * *")).toMatchObject({ mode: "monthly", time: "02:10", monthDay: "15" });
  });

  it("keeps unsupported expressions as custom", () => {
    expect(parseSchedule("*/15 * * * *")).toMatchObject({ mode: "custom", custom: "*/15 * * * *" });
  });
});
