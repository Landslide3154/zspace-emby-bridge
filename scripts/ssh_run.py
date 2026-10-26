"""在 NAS 上执行一条命令（只读优先），输出到本地。

用法：
  python scripts/ssh_run.py "sqlite3 ..."
  python scripts/ssh_run.py --sudo "sqlite3 ..."   # 走 sudo，密码从 .env 读，不进命令行
"""
from __future__ import annotations

import pathlib
import sys

import paramiko


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
    args = sys.argv[1:]
    use_sudo = "--sudo" in args
    command = " ".join(a for a in args if a != "--sudo").strip()
    if not command:
        print('用法：python scripts/ssh_run.py [--sudo] "<命令>"')
        raise SystemExit(2)

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
    remote = f"sudo -S -p '' bash -lc {shell_quote(command)}" if use_sudo else command
    stdin, stdout, stderr = client.exec_command(remote, timeout=60, get_pty=False)
    if use_sudo:
        stdin.write(env["ZSPACE_PASS"] + "\n")
        stdin.flush()
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    print(out.rstrip())
    if err.strip():
        print("[stderr]", err.strip())
    print("[exit]", stdout.channel.recv_exit_status())
    client.close()


def shell_quote(text: str) -> str:
    return "'" + text.replace("'", "'\\''") + "'"


if __name__ == "__main__":
    main()
