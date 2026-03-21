import os
import subprocess
from pathlib import Path


if os.getenv("SYNCHRONIZER_ENABLED") == "true":
    # By default subprocess.run doesn't throw error if the command was failed due runtime and pod completes without any errors
    # with check = True subprocess.run will throw error and pod will be completed with error
    repository = os.getenv("ENV_REPOSITORY", "")
    repository_dir = Path(repository.rsplit("/", 1)[-1])
    helmfile_path = repository_dir / os.getenv("PATH_TO_HELMFILE", "")

    subprocess.run(["git", "clone", f"https://github.com/{repository}.git"], check=True)
    subprocess.run(["helmfile", "cache", "cleanup"], check=True)
    subprocess.run(
        [
            "helmfile",
            "--environment",
            f'{os.getenv("NAMESPACE")}',
            "--namespace",
            f'{os.getenv("NAMESPACE")}',
            "-f",
            str(helmfile_path),
            "apply",
        ],
        check=True,
    )
else:
    print("SYNCHRONIZER IS DISABLED")
