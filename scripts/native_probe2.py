"""探测极影视原生接口：record/list（读）与 video/updateplaytime（写）。

只打印状态码、字段名和必要数值，不打印 token。
"""
from __future__ import annotations

import json
import pathlib

import httpx

OUT = pathlib.Path("data/native_probe")
OUT.mkdir(parents=True, exist_ok=True)


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
    base = env["ZSPACE_BASE_URL"].rstrip("/")
    common = {
        "token": env["ZSPACE_TOKEN"],
        "nasid": env["ZSPACE_NAS_ID"],
        "device_id": env["ZSPACE_DEVICE_ID"],
        "plat": "web",
        "version": env["ZSPACE_VERSION"],
        "_l": "zh_cn",
    }

    with httpx.Client(base_url=base, timeout=15.0, trust_env=False) as client:
        records = client.post("/zvideo/record/list", data={**common, "page": 1, "limit": 10})
        _save("record_list", records)
        payload = records.json()
        print("record/list:", records.status_code, payload.get("code"), payload.get("msg"))
        data = payload.get("data")
        if isinstance(data, dict):
            print("  data keys:", sorted(data)[:10])
            for key in ("list", "items", "records"):
                if isinstance(data.get(key), list):
                    first = data[key][0] if data[key] else {}
                    print(f"  {key}: len={len(data[key])} first_keys={sorted(first)[:14]}")
                    print("  first_sample:", json.dumps(first, ensure_ascii=False)[:400])
        elif isinstance(data, list):
            print("  list len:", len(data), "first_keys:", sorted(data[0])[:14] if data else [])

        for name, extra in (
            ("update_min", {"collection_id": "560a79a3e816b6e", "play_time": 300}),
            ("playlist", {"collection_id": "560a79a3e816b6e"}),
        ):
            path = "/zvideo/video/updateplaytime" if name == "update_min" else "/zvideo/video/v2/playlist"
            response = client.post(path, data={**common, **extra})
            _save(name, response)
            body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            print(path, response.status_code, body.get("code"), body.get("msg"))
            print("  sample:", response.text[:200])


def _save(name: str, response: httpx.Response) -> None:
    (OUT / f"{name}.json").write_text(response.text, encoding="utf-8")


if __name__ == "__main__":
    main()
