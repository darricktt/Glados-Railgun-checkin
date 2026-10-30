# Glados自动签到

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


## 问题排查与定位
- 大家可以通过查询 actions 中的 running checkin 日志快速定位问题，有其他问题提交issue。

- HTTP 200 或 Actions 步骤执行完毕不等于签到成功。脚本按 Cookie 判定退出状态：每个 Cookie 至少在 `glados.cloud`、`railgun.info` 中的一个域名成功或今日已签到，才返回 `0`；任一 Cookie 在两个域名均失败、没有 Cookie 或执行异常时返回 `1`，Actions 显示失败。汇总中的成功／失败／重复数量仍按域名任务统计。
- 兑换请求以 `application/json` 发送 `planType`，避免服务端因缺少 JSON Content-Type 返回 `Plan type is required`。
- 离线验证：安装 workflow 中已有的 `requests`、`pypushdeer` 依赖后运行 `python -m unittest discover -s tests -v`。测试使用模拟响应，不签到、不兑换、不发送推送。

  <img width="1684" height="844" alt="image" src="https://github.com/user-attachments/assets/45348a5f-43e4-45f5-8fdf-ce84d343b30d" />

## 声明

本项目不保证稳定运行与更新, 因GitHub相关规定可能会删库, 请注意备份







