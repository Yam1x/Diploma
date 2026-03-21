from __future__ import annotations


def test_minio_objects_api_returns_bucket_contents(client) -> None:
    response = client.get("/api/minio/objects", params={"prefix": "archive/"})

    assert response.status_code == 200
    payload = response.json()

    assert payload["bucketName"] == "backups"
    assert payload["prefix"] == "archive/"
    assert payload["objects"][0]["key"] == "archive/db/2026-03-21.dump"
    assert payload["objects"][1]["key"] == "archive/s3/2026-03-21.tar.gz"
