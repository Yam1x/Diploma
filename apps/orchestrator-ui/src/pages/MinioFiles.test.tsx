import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, test, vi } from "vitest";

const { api } = vi.hoisted(() => ({
  api: {
    listMinioObjects: vi.fn(),
  },
}));

vi.mock("../api/client", () => ({ api }));

import { MinioFilesPage } from "./MinioFiles";

beforeEach(() => {
  vi.clearAllMocks();
  api.listMinioObjects.mockResolvedValue({
    bucketName: "backups",
    prefix: "",
    objects: [
      {
        key: "db/2026-03-21.dump",
        size: 4096,
        lastModified: "2026-03-21T08:30:00Z",
        etag: "etag-1",
      },
    ],
  });
});

test("renders minio objects and applies prefix filter", async () => {
  const user = userEvent.setup();

  render(<MinioFilesPage />);

  expect(await screen.findByText("db/2026-03-21.dump")).toBeInTheDocument();
  expect(api.listMinioObjects).toHaveBeenCalledWith("");

  api.listMinioObjects.mockResolvedValueOnce({
    bucketName: "backups",
    prefix: "archive/",
    objects: [
      {
        key: "archive/s3/2026-03-21.tar.gz",
        size: 8192,
        lastModified: "2026-03-21T09:00:00Z",
        etag: "etag-2",
      },
    ],
  });

  await user.clear(screen.getByPlaceholderText("archive/"));
  await user.type(screen.getByPlaceholderText("archive/"), "archive/");
  await user.click(screen.getByRole("button", { name: "Применить" }));

  await waitFor(() => expect(api.listMinioObjects).toHaveBeenLastCalledWith("archive/"));
  expect(await screen.findByText("archive/s3/2026-03-21.tar.gz")).toBeInTheDocument();
});
