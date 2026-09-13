#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""上游响应解包代理（本地 127.0.0.1:8899）

背景：有些 OpenAI 兼容上游（例：api.cline.bot）在 **非流式** 请求下会把整个响应
包一层壳：{"data": {..choices..}, "success": true}，顶层没有 choices。
Hermes 的 cron / 子代理路径为了线程池安全走 **非流式** 直连，于是解析失败，报
"Invalid API response: response.choices is None"。

本代理把上游请求原样转发，收到响应后：
  - 若是 {"data": {...}} 包壳（且 data 里有 choices）→ 解包成标准 OpenAI 形状返回
  - 若是 /models → 解包成 {"object":"list","data":[...]}
  - 其他情况原样透传（包括流式 SSE）

用法：
  python3 cline_unwrap_proxy.py [--port 8899]
  nohup python3 cline_unwrap_proxy.py >> ~/.hermes/logs/unwrap_proxy.log 2>&1 &

建议装成 systemd 服务（Restart=always，开机自启），另加一个每 10 分钟看门狗 cron
（端口没在听就拉起，正常则静默）。

配套 provider（config.yaml）：
  providers:
    <名>:
      base_url: http://127.0.0.1:8899/v1
      key_env: <读 key 的环境变量名>
      api_mode: chat_completions
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = os.environ.get("UNWRAP_UPSTREAM", "https://api.cline.bot/api/v1")
ENV_FILE = os.path.expanduser("~/.hermes/.env")


def env_key(name="CUSTOM_CLINE_2_API_KEY"):
    try:
        for line in open(ENV_FILE, encoding="utf-8"):
            line = line.strip()
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return ""


def unwrap(raw: bytes, path: str) -> bytes:
    """把 {"data": ...} 包壳解成标准 OpenAI 形状；解不动就原样返回。"""
    try:
        obj = json.loads(raw.decode("utf-8"))
    except Exception:
        return raw
    if not isinstance(obj, dict):
        return raw
    payload = obj.get("data") if isinstance(obj.get("data"), dict) else None
    if path.endswith("/models"):
        if isinstance(obj.get("data"), list):
            return json.dumps({"object": "list", "data": obj["data"]}).encode("utf-8")
        return raw
    if payload is not None and payload.get("choices") is not None:
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if payload is not None and obj.get("success") is False:
        msg = payload.get("message") or payload.get("error") or "upstream error"
        return json.dumps({"error": {"message": str(msg), "type": "upstream_error"}}).encode("utf-8")
    return raw


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):
        sys.stderr.write("[unwrap-proxy] " + fmt % a + "\n")
        sys.stderr.flush()

    def _upstream_path(self) -> str:
        p = self.path.split("?", 1)[0]
        if p.endswith("/chat/completions"):
            return "/chat/completions"
        if p.endswith("/models"):
            return "/models"
        return p

    def _proxy(self, method: str):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        headers = {"Content-Type": "application/json"}
        headers["Authorization"] = self.headers.get("Authorization") or ("Bearer " + env_key())
        req = urllib.request.Request(UPSTREAM + self._upstream_path(), data=body,
                                     headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                raw = r.read()
                ctype = r.headers.get("Content-Type", "application/json")
                status = r.status
        except urllib.error.HTTPError as e:
            raw = e.read() or b"{}"
            ctype = e.headers.get("Content-Type", "application/json")
            status = e.code
        except Exception as e:
            raw = json.dumps({"error": {"message": f"proxy upstream failure: {e}"}}).encode()
            ctype, status = "application/json", 502
        if "text/event-stream" in ctype or raw.lstrip().startswith(b"data:"):
            out, ctype = raw, "text/event-stream; charset=utf-8"
        else:
            out, ctype = unwrap(raw, self._upstream_path()), "application/json; charset=utf-8"
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(out)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(out)

    def do_POST(self):
        self._proxy("POST")

    def do_GET(self):
        self._proxy("GET")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    sys.stderr.write(f"[unwrap-proxy] listening on http://{a.host}:{a.port} -> {UPSTREAM}\n")
    sys.stderr.flush()
    srv.serve_forever()
