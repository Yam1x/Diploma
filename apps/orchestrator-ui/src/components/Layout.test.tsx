import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, test, vi } from "vitest";

const { api } = vi.hoisted(() => ({
  api: {
    listNotifications: vi.fn(),
    markNotificationRead: vi.fn(),
    markAllNotificationsRead: vi.fn(),
  },
}));

vi.mock("../api/client", () => ({ api }));

import { Layout } from "./Layout";

beforeEach(() => {
  vi.clearAllMocks();
  api.listNotifications.mockResolvedValue({ unreadCount: 0, items: [] });
  api.markNotificationRead.mockResolvedValue(undefined);
  api.markAllNotificationsRead.mockResolvedValue(undefined);
});

test("renders sidebar with backup and minio sections", async () => {
  render(
    <MemoryRouter initialEntries={["/minio-files"]}>
      <Layout>
        <div>content</div>
      </Layout>
    </MemoryRouter>,
  );

  expect(screen.getByText("Сервисы бэкапирования")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Настройка сервисов" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Просмотр файлов в MinIO" })).toHaveClass("active");
  expect(await screen.findByText("content")).toBeInTheDocument();
});

test("does not start interval polling for notifications", async () => {
  const setIntervalSpy = vi.spyOn(window, "setInterval");

  render(
    <MemoryRouter initialEntries={["/"]}>
      <Layout>
        <div>content</div>
      </Layout>
    </MemoryRouter>,
  );

  expect(await screen.findByText("content")).toBeInTheDocument();
  expect(api.listNotifications).toHaveBeenCalledTimes(1);
  expect(setIntervalSpy).not.toHaveBeenCalled();

  setIntervalSpy.mockRestore();
});
