"""把项目上传到 NAS 的临时目录，供 docker build 使用（不传凭据）。"""
from __future__ import annotations

import pathlib

import paramiko

REMOTE_DIR = "/tmp/zspace-emby-bridge"

CONTAINER_ENV = """UPSTREAM_URL=http://192.168.2.8:8021
LISTEN_PORT=8022
DB_PATH=/data/progress.db
LOG_LEVEL=INFO
TZ=Asia/Shanghai
PLAYED_THRESHOLD=0.9
NATIVE_MODE=local
NATIVE_DB_PATH=/zvideo/zvideo.db
NATIVE_USER=17611545258
NATIVE_MIN_INTERVAL=10
SYNC_GRACE_SECONDS=15
SYNC_STREAM_PREFS=true
ADMIN_PASSWORD=
"""


def load_env(path: str = ".env") -> dict[str, str]:
    env: dict[str, str] = {}
    for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def main() -> None:
    env = load_env()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=env["ZSPACE_SSH_HOST"],
        port=int(env["ZSPACE_SSH_PORT"]),
        username=env["ZSPACE_SSH_USER"],
        password=env["ZSPACE_PASS"],
        timeout=10,
        allow_agent=False,
        look_for_keys=False,
    )
    sftp = client.open_sftp()
    for folder in (REMOTE_DIR, f"{REMOTE_DIR}/app"):
        try:
            sftp.stat(folder)
        except OSError:
            sftp.mkdir(folder)
    for name in ("Dockerfile", "pyproject.toml"):
        sftp.put(name, f"{REMOTE_DIR}/{name}")
    for path in sorted(pathlib.Path("app").glob("*.py")):
        sftp.put(str(path), f"{REMOTE_DIR}/app/{path.name}")
    with sftp.file(f"{REMOTE_DIR}/.env", "w") as handle:
        handle.write(CONTAINER_ENV)
    sftp.close()
    client.close()
    print("已上传到", REMOTE_DIR)


if __name__ == "__main__":
    main()
