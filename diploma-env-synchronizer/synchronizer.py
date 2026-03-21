import subprocess
import os

if (os.getenv("SYNCHRONIZER_ENABLED") == "true"):
    # By default subprocess.run doesn't throw error if the command was failed due runtime and pod completes without any errors
    # with check = True subprocess.run will throw error and pod will be completed with error
    subprocess.run(['git', 'clone', f'https://github.com/{os.getenv("ENV_REPOSITORY")}.git'], check = True)

    subprocess.run(['helmfile', 'cache', 'cleanup'], check = True)

    subprocess.run(['helmfile', '--environment', f'{os.getenv("NAMESPACE")}', '--namespace', f'{os.getenv("NAMESPACE")}', '-f', f'{os.getenv("PATH_TO_HELMFILE")}', 'apply'], check = True)

else:
    print("SYNCHRONIZER IS DISABLED")