# 签到请求与失败状态修复

用户确认范围：支持自行配置 UA，修复兑换请求的 JSON 格式，并让签到失败反映为 Actions 失败。用户自行更新 Cookie 与 UA。

采用最小改动：`GLADOS_USER_AGENT` 由 Actions Secret 注入 Config，并传递到所有 API 请求；空值兼容旧默认 UA。相比写死新版本 UA，此方式可与真实登录会话保持一致。POST 统一使用 requests 的 `json=` 参数，让请求体与 Content-Type 一致。

现有逻辑会在两个域名尝试每个 Cookie，因此退出状态按 Cookie 聚合。每个 Cookie 至少有一个成功或今日已签到的域名才算通过；任一 Cookie 全部失败、无 Cookie 或执行异常返回 1。相比任一域名失败就退出，此规则适用于只在一个站点有效的 Cookie。推送在返回退出码前保持原流程；失败时仍运行保活步骤。

验证计划：使用真实 requests 请求准备流程与模拟响应核对 UA、Cookie、JSON 请求体和 Content-Type；覆盖签到成功、重复、拒绝、多账号部分失败、网络异常、缺少 Cookie 和 CLI 退出码。新增独立离线测试 workflow，不读取账号密钥、不调用真实签到或兑换。
