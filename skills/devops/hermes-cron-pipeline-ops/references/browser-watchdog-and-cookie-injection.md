# 浏览器看门狗 + Cookie 注入：headless Chrome 的静默死亡与自动恢复

## 问题

脚本化流水线（微头条 `wt_pipeline.sh` 等）依赖一个长期存活的 headless Chrome（9222 端口，
`--user-data-dir=/tmp/chrome-wx`，同时承载头条 + DeepSeek 网页版的登录态）。

**Chrome 会在夜间静默死亡**（实测：02:29 最后一次写入 History，之后 9222 消失，无任何报错）。
流水线第 1 步要连 9222 抓热榜 → `Connection refused` → 整班失败。
因为脚本只报「第 1 步失败」，下一次班也照旧失败，形成**连挂 N 小时的静默腐烂**
（实测 03:00/04:00/05:00/06:00/07:00 连挂 5 班）。

**排错铁律**：脚本化流水线连续失败时，**先查基础设施依赖**（浏览器、代理、daemon），
再查模型/业务逻辑。不要看到「Connection refused」就去修脚本——脚本没错，是依赖死了。

## 修法：脚本内看门狗

在流水线脚本**最开头**（做任何事之前）探 9222，挂了就按原参数自动拉起：

```bash
# 探活 + 自动拉起（最多等 30s）
for i in $(seq 1 30); do
  curl -s -m 2 http://127.0.0.1:9222/json/version >/dev/null 2>&1 && break
  if [ $i -eq 1 ]; then
    nohup /opt/google/chrome/chrome --headless=new --disable-gpu \
      --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-wx \
      --no-sandbox --noerrdialogs --ozone-platform=headless \
      > /tmp/chrome_start.log 2>&1 &
  fi
  sleep 1
done
curl -s -m 3 http://127.0.0.1:9222/json/version >/dev/null 2>&1 \
  || fail_and_mail "Chrome 9222 拉不起来"
```

关键点：
- `--user-data-dir` 必须用**同一个目录**，登录态（cookie / localStorage）都在里面
- 放在脚本最开头，不要放在第 1 步业务逻辑里——否则业务报错时浏览器还是挂的
- 拉不起来（30s 内）才发邮件告警，不要静默失败

## Cookie 注入：重启后验证登录态

Chrome 重启后 `/tmp/chrome-wx` 里的 cookie **可能还在，也可能过期**。
不能假设「目录在 = 登录态在」。验证方法：

`scripts/inject_toutiao_cookie.py`（CDP `Network.setCookie` 注入存好的
`sessionid` / `sessionid_ss` → 导航到发布页 → 检查 URL 没跳登录页 +
`.ProseMirror` 编辑器就绪）。

判断标准：
- URL 含 `/login` 或 `/sso` → sessionid 已失效，需要重新获取
- `.ProseMirror` 编辑器存在 → 登录成功
- 两者都不满足（URL 对了但没编辑器）→ 页面还在加载，等几秒再看

## 存 cookie 的位置

`<skill>/config/toutiao_cookies.json`：

{"domain": ".toutiao.com", "cookies": [
  {"name": "sessionid", "value": "..."},
  {"name": "sessionid_ss", "value": "..."}
]}

用户手动提供时存这里；脚本注入时读这里。**不要把 cookie 值写进 SKILL.md 或日志**。

## 适用场景

任何「cron 脚本 + 长期存活的 headless Chrome + cookie 登录态」的组合：
微头条发布、DeepSeek 网页版终审、任何需要保持登录态的自动化。

