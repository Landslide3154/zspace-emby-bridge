"""SSH 只读勘察：确认极影视的 zvideo.db 位置与表结构。

只执行读命令，不修改任何文件；输出里不含密码。
"""
from __future__ import annotations

import pathlib

import paramiko

CANDIDATE_USERS = ("root", "17611545258", "admin")


def load_env(path: str = ".env") -> dict[str, str]:
    env: dict[str, str] = {}
    for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def run(client: paramiko.SSHClient, command: str) -> str:
    _, stdout, stderr = client.exec_command(command, timeout=20)
    out = stdout.read().decode("utf-8", "replace").strip()
    err = stderr.read().decode("utf-8", "replace").strip()
    return (out + ("\n[stderr] " + err if err else "")).strip()


def main() -> None:
    env = load_env()
    host = env["ZSPACE_SSH_HOST"]
    port = int(env["ZSPACE_SSH_PORT"])
    password = env["ZSPACE_PASS"]
    for user in CANDIDATE_USERS:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=host,
                port=port,
                username=user,
                password=password,
                timeout=8,
                allow_agent=False,
                look_for_keys=False,
            )
        except paramiko.AuthenticationException:
            print(f"{user}: 认证失败")
            client.close()
            continue
        except Exception as exc:  # 网络/协议错误
            print(f"{user}: 连接失败 {type(exc).__name__}: {exc}")
            client.close()
            return
        print(f"{user}: 登录成功")
        for command in (
            "uname -a",
            "id",
            "ls -l /zspace/zsrp/sqlite/zvideo 2>&1 | head -10",
            "command -v sqlite3 python3 python 2>&1",
        ):
            print(f"$ {command}")
            print(run(client, command))
        client.close()
        return
    print("所有候选用户名都认证失败")


if __name__ == "__main__":
    main()
