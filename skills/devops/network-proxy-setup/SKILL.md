---
name: network-proxy-setup
description: "Use when setting up system proxy on Linux or GitHub access."
---

# Network Proxy Setup on Linux (mihomo / Clash)

Validated workflow for turning a Clash subscription URL into a persistent system proxy on a Linux box.

## Workflow

1. **Fetch the subscription config** with plain `curl` (a HEAD request may be rejected with 405 by some panels — always do a full GET):
   ```bash
   curl -s -m 30 -o /tmp/sub.yaml "<SUB_URL>" -w "%{http_code} %{size_download}\n"
   head -30 /tmp/sub.yaml   # read mixed-port, proxy types, node names
   ```
   Note `mixed-port` (use it everywhere below; commonly 9981) and node credentials.

2. **Bootstrap-download mihomo THROUGH a node from the subscription itself.** Direct GitHub downloads from a censored network often hang/timeout silently. Extract one node's HTTP/SOCKS5 creds from the config and use it as the curl proxy:
   ```bash
   curl -sL -m 100 -x "http://USER:PASS@SERVER:443" \
     -o /tmp/mihomo.gz "https://github.com/MetaCubeX/mihomo/releases/download/v1.18.10/mihomo-linux-amd64-v1.18.10.gz"
   ```
   This chicken-and-egg trick (proxy downloads the proxy) is the key step.

3. **Install + first run**:
   ```bash
   gunzip /tmp/mihomo.gz && chmod +x /tmp/mihomo && sudo mv /tmp/mihomo /usr/local/bin/mihomo
   sudo mkdir -p /etc/mihomo && sudo cp /tmp/sub.yaml /etc/mihomo/config.yaml
   ```

4. **CRITICAL PITFALL — MMDB hangs startup.** On first run mihomo tries to download `Country.mmdb` from GitHub; on a censored network this hangs FOREVER (process alive, zero log progress, port never listens). Fix: kill it and pre-download the MMDB from a CDN mirror:
   ```bash
   sudo curl -sL -m 60 -o /etc/mihomo/country.mmdb \
     "https://cdn.jsdelivr.net/gh/MetaCubeX/meta-rules-dat@release/country.mmdb"
   ```
   Symptom signature: log stops at `"Can't find MMDB, start download"`, port not listening, `pgrep` shows process running. Pre-seeding the file fixes it immediately.

5. **Persist as systemd service**:
   ```ini
   # /etc/systemd/system/mihomo.service
   [Unit]
   Description=Mihomo Proxy
   After=network.target
   [Service]
   ExecStart=/usr/local/bin/mihomo -d /etc/mihomo
   Restart=on-failure
   [Install]
   WantedBy=multi-user.target
   ```
   Then `sudo systemctl enable --now mihomo`.

6. **System-wide env vars** (both files; /etc/environment alone misses some contexts, /etc/profile.d alone misses cron):
   - `/etc/environment`: `http_proxy="http://127.0.0.1:PORT"`, `https_proxy=...`, `no_proxy="localhost,127.0.0.1"`
   - `/etc/profile.d/proxy.sh`: same as `export` lines
   - git: `git config --global http.proxy http://127.0.0.1:PORT`

## Verification
- `curl -s -m 15 -x http://127.0.0.1:9981 https://api.github.com -o /dev/null -w "%{http_code}"` → 200
- Real clone test (some endpoints are rate-limited/slow even when proxy works):
  `git -c http.proxy=http://127.0.0.1:9981 clone --depth 1 https://github.com/octocat/Hello-World.git /tmp/hw`
- Do NOT conclude the proxy is broken from a single failing endpoint: `codeload.github.com` may 429 and huge `ls-remote` on giant repos may time out while normal clone/API traffic works fine. Always test with a small repo.

## Gotchas
- The `terminal` tool forbids inline `&` backgrounding — run mihomo via `terminal(background=true)`, then verify the port in a follow-up call.
- Subscriptions expire/rotate; re-fetch config + `systemctl restart mihomo` to refresh.
- `allow-lan: true` in many subscription configs means the port listens on 0.0.0.0 — be aware before exposing a server.
- The MMDB download may also succeed directly via a jsdelivr/raw mirror even when GitHub raw is unreachable; jsdelivr is the reliable first choice.
- First curl attempt to GitHub with `-I` (HEAD) got 405 from the panel — panels often only accept GET. The subscription fetch itself usually succeeds even when GitHub does not.

## Skills batch-install pattern
Bulk-installing skills from a git repo (e.g. clone repo, copy `skills/*/` into `~/.hermes/skills/`): repo may contain `@user/` subdirectories each holding more skills — flatten those (`for f in @*/*/; do cp -r "$f" ~/.hermes/skills/; done`) and skip `@*` top-level dirs. Verify with `skills_list` count before/after; some third-party SKILL.md files have malformed frontmatter (e.g. description literally `---`) — note these rather than silently skipping the skill.
