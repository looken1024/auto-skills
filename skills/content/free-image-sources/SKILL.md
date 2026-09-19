---
name: free-image-sources
description: Choose a free image source by quality and licensing.
---

# Free Image Sources

Decision matrix for choosing a free image source when you need photos or AI-generated images without paying.

## Quick Decision

| Need | Use | Why |
|------|-----|-----|
| Real photos, best quality, keyword search | **Pexels** | API key required (free), highest quality, photographer attribution |
| Real photos, no API key, keyword search | **LoremFlickr** | Free, keyword-based, but prone to duplicates |
| Real photos, no API key, any image | **Picsum** | Free, high-res random images, no keyword search |
| AI-generated images, no key | **pollinations.ai** | Free, text-to-image, vertical max 576×1024 |

## Source Details

### Pexels (primary for photo galleries)
- API key stored in `~/hermes/skills/douyin-card-pipeline/config.json` (`pexels_api_key`)
- Quality: best — 1200+px horizontal, photographer metadata, consistent resolution
- Rate limits: watch for 429s; fallback to LoremFlickr
- Used by: `wechat-ai-publisher` gallery pipeline, `douyin-card-pipeline`

### LoremFlickr (fallback / no-key option)
- No API key needed
- URL pattern: `https://loremflickr.com/1200/800/{keywords}?lock={N}`
- **Pitfall**: `lock` parameter does NOT guarantee unique images — multiple requests can return identical file sizes (duplicate). Always verify visually or check file sizes before assuming uniqueness.
- Use as fallback when Pexels is rate-limited or down
- Example: `https://loremflickr.com/1200/800/snow,mountain,lake?lock=7`

### Picsum (random only)
- No API key, `https://picsum.photos/1200/800`
- No keyword search — purely random Unsplash mirror
- Good when you just need any high-res image with zero setup

### pollinations.ai (AI generation)
- No API key, text-to-image via URL: `https://pollinations.ai/image/{prompt}?width=576&height=1024`
- Max 576×1024 vertical, watermark at bottom-right (crop ~52px)
- Used by: `ima-image-pipeline`
- Note: quality is lower than real photos; good for abstract/thematic images

## Blocked / Unavailable from This Host

These sources were tested and confirmed unreachable or unusable from this host's network:

- **Openverse** (api.openverse.org) — DNS resolves but TCP unreachable; both direct and proxy routes fail
- **Wikimedia Commons** — same network issue
- **Unsplash source** — official free endpoint officially shut down (returns 503)
- **Pixabay** — requires API key application (free but审核 slow); not usable without key
- **Tuchong / 图虫** (tuchong.com) — homepage loads but all content pages (tags, explore, hot) return 403 for unauthenticated headless browsers; images are copyright-protected anyway
- **Xiaohongshu / 小红书** — IP-blocked with error 300012 ("IP存在风险"); blocks datacenter IPs including domestic Tencent Cloud IPs; not fixable by bypassing proxy or changing UA

## Chrome Proxy Bypass

When a site appears blocked due to proxy routing (e.g., Chrome going through mihomo when direct access is needed):

1. Kill the existing Chrome: `pkill -f remote-debugging-port=9222`
2. Restart with proxy environment variables cleared:
   ```bash
   env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY \
     /opt/google/chrome/chrome --headless=new --disable-gpu \
     --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-wx \
     --no-sandbox --noerrdialogs --ozone-platform=headless
   ```
3. Verify the new process has no proxy vars: check `/proc/<pid>/environ` for `proxy` entries
4. Test出口 IP via `fetch('https://api.ipify.org')` in browser or `curl` directly

**Note**: This only helps when the block is proxy-related. Xiaohongshu and Tuchong block datacenter IPs regardless of proxy — bypassing the proxy won't help there.

## Adding a New Source

When evaluating a new image source, test in this order:
1. Does it need an API key? (If yes, can you get one quickly?)
2. Can you reach it from this host? (Direct curl, proxy curl, and browser fetch — test all three)
3. Does it support keyword search? (Random-only sources are limited)
4. What's the licensing? (CC0/CC-BY for commercial use; copyright = unusable for publishing)
5. What's the image quality and consistency? (Check file sizes for duplicates, resolution for sharpness)
