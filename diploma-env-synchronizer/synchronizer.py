import logging
import os
import subprocess
from pathlib import Path


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [env-synchronizer] %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    if os.getenv("SYNCHRONIZER_ENABLED") != "true":
        logger.info("Synchronizer is disabled")
        return

    # By default subprocess.run doesn't throw error if the command was failed due runtime and pod completes without any errors
    # with check = True subprocess.run will throw error and pod will be completed with error
    repository = os.getenv("ENV_REPOSITORY", "")
    namespace = os.getenv("NAMESPACE")
    repository_dir = Path(repository.rsplit("/", 1)[-1])
    helmfile_path = repository_dir / os.getenv("PATH_TO_HELMFILE", "")

    logger.info("Starting synchronization for repository %s into namespace %s", repository, namespace)
    try:
        logger.info("Cloning repository %s", repository)
        subprocess.run(["git", "clone", f"https://github.com/{repository}.git"], check=True)
        logger.info("Cleaning helmfile cache")
        subprocess.run(["helmfile", "cache", "cleanup"], check=True)
        logger.info("Applying helmfile %s", helmfile_path)
        subprocess.run(
            [
                "helmfile",
                "--environment",
                f"{namespace}",
                "--namespace",
                f"{namespace}",
                "-f",
                str(helmfile_path),
                "apply",
            ],
            check=True,
        )
        logger.info("Synchronization completed successfully")
    except subprocess.CalledProcessError:
        logger.exception("Synchronization failed")
        raise


if __name__ == "__main__":
    main()
