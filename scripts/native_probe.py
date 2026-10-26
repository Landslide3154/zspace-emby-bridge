"""一次性探测：极空间原生登录（RSA 加密）→ zvideo 接口。

只打印状态码与字段名，绝不打印密码 / token / cookie 值。
"""
from __future__ import annotations

import base64
import pathlib

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding


def load_env(path: str = ".env") -> dict[str, str]:
    env: dict[str, str] = {}
    for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def brief(response: httpx.Response, max_items: int = 5) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"http={response.status_code} 非JSON"
    if not isinstance(payload, dict):
        return f"http={response.status_code} list_len={len(payload)}"
    data = payload.get("data")
    if isinstance(data, dict):
        shape = f"data_keys={sorted(data)[:8]}"
    elif isinstance(data, list):
        shape = f"data_list_len={len(data)}"
    else:
        shape = f"data={type(data).__name__}"
    return f"http={response.status_code} code={payload.get('code')} msg={payload.get('msg')} {shape}"


def rsa_b64(public_pem: str, text: str) -> str:
    key = serialization.load_pem_public_key(public_pem.encode())
    cipher = key.encrypt(text.encode(), padding.PKCS1v15())
    return base64.b64encode(cipher).decode()


def main() -> None:
    env = load_env()
    base = env["ZSPACE_BASE_URL"].rstrip("/")
    with httpx.Client(base_url=base, timeout=10.0, follow_redirects=True, trust_env=False) as client:
        pub = client.get("/key/pub").json()["data"]["key"]
        print("key/pub: 拿到 RSA 公钥，长度", len(pub))
        login = client.post(
            "/auth/login",
            data={
                "username": rsa_b64(pub, env["ZSPACE_USER"]),
                "password": rsa_b64(pub, env["ZSPACE_PASS"]),
                "plat": "web",
                "webagent": "v2",
                "rnd": "1",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        print("login:", brief(login))
        print("cookies:", sorted(cookie.name for cookie in client.cookies.jar))
        print("record/list:", brief(client.post("/zvideo/record/list", json={})))
        print("video/randomlist:", brief(client.post("/zvideo/video/randomlist", json={})))


if __name__ == "__main__":
    main()
