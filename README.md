# Glados自动签到

当前版本只访问 `glados.cloud`，已停用 Railgun。默认通过标准 Chromium 打开官网签到页面、点击 `Checkin` 按钮，并以官网接口的业务结果判断成功。官网负责获取 challenge、执行 Turnstile 和提交验证；脚本不生成或伪造 Turnstile token。

GitHub Actions 会自动安装锁定的运行依赖和 Chromium。浏览器验证可以无感通过，也可能需要人工操作；云端运行不保证通过交互验证。失败时保留原因并返回非零退出码，不自动退回 HTTP 方式。

本机可见浏览器模式：先安装 `python -m pip install -r requirements.lock` 和 `python -m playwright install chromium`，在本机环境设置 `GLADOS_COOKIES`、`GLADOS_USER_AGENT` 后运行：

```sh
GLADOS_CHECKIN_MODE=browser GLADOS_BROWSER_HEADLESS=false GLADOS_VERIFY_ONLY=true python checkin.py
```

浏览器打开后可按官网提示完成验证，默认最多等待两分钟。`GLADOS_VERIFY_ONLY=true` 会跳过兑换和推送；确认正常后可以移除此设置。GitHub 手动运行时也可勾选 `verify_only`。如需保留旧 HTTP 请求方式，可设置 Actions 仓库 Variable `GLADOS_CHECKIN_MODE=http`，但 HTTP 模式无法完成 Turnstile。

离线测试：运行 `python -m unittest discover -s tests -v`；设置 `GLADOS_RUN_BROWSER_TESTS=1` 后还会运行真实 Chromium 的模拟页面测试，所有请求均被拦截，不接触真实账号。依赖来源与准确版本见 `requirements.txt`、`requirements.lock`，Playwright 来源为 [Microsoft Playwright](https://github.com/microsoft/playwright-python)。

## 食用方式：

### 注册一个GLaDOS的账号([注册地址](https://glados.space/landing/0A58E-NV28S-6U3QV-33VMG))

#### 我的邀请码：([0A58E-NV28S-6U3QV-33VMG](https://0a58e-nv28s-6u3qv-33vmg.glados.space)) 

### **Fork**本仓库

![图片加载失败](imgs/1.png)

### 添加**secret**

1. 跳转至自己的仓库的`Settings`->`Secrets and variables`->`Action`

2. 添加1个`repository secret`，命名为`GLADOS_COOKIES`，其值对应GLaDOS账号的cookie值中的有效部分（获取方式如下）

- 在GLaDOS的签到页面按`F12`

- 切换到`Network`页面下，刷新

![图片加载失败](imgs/2.png)

- 点击第一个选项卡后在`Request Headers`下找到`Cookie`，右键复制cookie的值即可

  > 参考格式：koa:sess=eyJ1c2xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxAwMH0=; koa:sess.sig=xJkOxxxxxxxxxxxxxxxtnM;

![图片加载失败](imgs/3.png)

- 多账号请在 `COOKIES` 中 添加多个 `cookies` 中间使用 `&`连接即可。（例如： `c1&c3&c3...`）

### 配置登录浏览器的 User-Agent

添加 Actions repository secret `GLADOS_USER_AGENT`，填写获取当前 Cookie 时浏览器发送的完整 `User-Agent`。脚本的签到、状态查询、积分查询和兑换请求均使用此值；未设置或仅为空白时沿用默认 UA。

遇到 `Automated check-in detected` 或设备不匹配时，在实际使用的站点重新登录，从开发者工具 `Network` 中同一次会话的 API 请求头复制完整 `Cookie` 和 `User-Agent`，同时更新 `GLADOS_COOKIES`、`GLADOS_USER_AGENT`。请保留网站实际发送的 Cookie 名称，不要手动把 `koa:sess` 改名为 `gld:sess`，也不要混用不同域名或新旧会话的值。多个账号共用一个 UA，获取各账号 Cookie 时应使用同一浏览器 UA。

仅添加 Secret 不会让旧代码读取它，请同时更新脚本及 workflow。此配置不保证服务端始终接受自动签到；更新后手动执行一次并检查业务结果。

3. 配置积分兑换策略（非必须）

- 添加1个`repository secret`，命名为`GLADOS_EXCHANGE_PLAN`，配置自动兑换积分策略：

| 值 | 积分要求 | 兑换天数 |
|---|---------|---------|
| `plan100` | 100 积分 | 10 天 |
| `plan200` | 200 积分 | 30 天 |
| `plan500` | 500 积分 | 100 天 (默认) |

> 不配置时默认为 `plan500`，即积分达到 500 时自动兑换 100 天

4. 手机推送（非必须）

- 添加1个`repository secret`，命名为`PUSHDEER_SENDKEY`，其值对应 PushDeer key: ([获取地址](https://www.pushdeer.com/product.html))。

### **star**自己的仓库

![图片加载失败](imgs/4.png)

## 文件结构

```shell
│  checkin.py	# 签到脚本
│
├─.github
│  └─workflows
│          gladosCheck.yml	# Actions 配置文件
```

## 更新日志

- **2026-01**: 重构代码，添加log输出方便定位，支持新版网址，支持配置积分兑换策略。
- **2026-04**: 优化代码逻辑，优化日志输出，支持[新版域名](https://railgun.info) ，在 GLADOS_COOKIES 中添加新版域名下的 cookies 即可使用。
- **2026-11-13**: 按当前官网分别适配 GLaDOS challenge／proof 和 Railgun token 签到流程，识别重复签到及 Turnstile 验证，签到失败后停止兑换。官网来源、哈希与验证范围见[流程核对记录](docs/checkin-flow-2026-11-13.md)。


## 问题排查与定位
- 大家可以通过查询 actions 中的 running checkin 日志快速定位问题，有其他问题提交issue。

- HTTP 200 或 Actions 步骤执行完毕不等于签到成功。每个 Cookie 都必须在 `glados.cloud` 成功或今日已签到，才返回 `0`；任一账号失败、没有 Cookie 或执行异常时返回 `1`，Actions 显示失败。
- 兑换请求以 `application/json` 发送 `planType`，避免服务端因缺少 JSON Content-Type 返回 `Plan type is required`。
- HTTP 模式每次签到获取新 challenge，等待至少 2.5 秒（脚本预留为 2.7 秒）后，向同一域名提交 nonce／proof。验证无效或要求 Turnstile 时明确失败。默认浏览器模式由官网页面执行完整流程。
- 浏览器模式仍提示验证失败时，可使用本机可见浏览器完成当次签到。刷新 Cookie 或改 UA 不能代替验证；失败原因会进入汇总。
- 首次签到获得 1／2 分仍算成功。GLaDOS 官网根据服务端返回的 `breakdown.freeCap` 显示免费账号上限；适配流程不承诺固定奖励或补发积分。请核对官网积分流水和账号提示。
- 只有签到成功或正常重复，且积分查询通过、余额达到当前兑换阈值时，脚本才发起兑换。
- 离线验证使用模拟响应，不签到、不兑换、不发送推送。请按本文开头的依赖与测试说明运行。

  <img width="1684" height="844" alt="image" src="https://github.com/user-attachments/assets/45348a5f-43e4-45f5-8fdf-ce84d343b30d" />

## 声明

本项目不保证稳定运行与更新, 因GitHub相关规定可能会删库, 请注意备份







