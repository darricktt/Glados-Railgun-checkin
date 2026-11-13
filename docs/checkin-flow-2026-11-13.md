# 2026 年 11 月 13 日官网签到流程核对

本轮基于仓库 `f431f8dfe5b9b80ffe77b2dc57a9c91d1fcd8b50` 适配官网当前发布的客户端。核对包含公开控制台 HTML、该 HTML 引用的脚本、相关动态路由与原始 proof 函数；没有使用真实账号触发签到或兑换。

## 观察到的流程

GLaDOS 控制台模块 631 从 `/api/user/checkin/challenge` 取得 `nonce`、毫秒单位的 `ttl` 和可选 `turnstile`。没有 Turnstile 时，客户端至少等待 2500 毫秒，并向同域 `/api/user/checkin` 提交 `token`、`nonce`、`proof`、`tsState: "off"`。`token` 是当前 hostname，proof 是 UTF-8 编码的 `nonce + ".glados-observe-v1"` 的 SHA-256 小写十六进制结果。

服务端启用 Turnstile 时，官网渲染验证组件，以 `checkin` 为 action、nonce 为 cData，等待真实 token，再将该 token 与 `tsState` 一起提交。脚本不实现交互式验证，遇到启用或无法识别的 Turnstile 元数据时停止，提示在官网手动完成签到。它不会将错误、超时或未完成验证伪装为 `off`。

Railgun `/console` 当前使用动态 chunk 26；其中的签到请求仍为 `/api/user/checkin`，请求体仅含 hostname token。`/console/checkin` 路由重定向到积分页，积分页本身不是签到按钮所在页面。两个站点不能直接套用相同的 challenge 流程。

两个站点的兑换请求均向 `/api/user/exchange` 提交对象 `{planType}`。关联 Axios 模块将对象序列化为 JSON，并声明 JSON Content-Type；本仓库保留 `requests` 的 `json=` 请求方式。没有采纳其他项目的 form 编码方式。

GLaDOS 当前客户端以 `code=0` 表示成功，并通过布尔字段 `repeated` 区分今日已签到。它还根据 `breakdown.freeCap` 显示免费账号积分上限；这是服务端提供的奖励信息，不由脚本设置。

## 来源与身份

下列 URL 均从当日官网 `/console` 的 HTML 或其动态路由映射中取得。SHA-256 标识核对的准确字节，不代表未来同一 URL 的内容不变。

| 官网文件 | 用途 | SHA-256 |
| --- | --- | --- |
| [GLaDOS 控制台](https://glados.cloud/static/js/main~21b3c6c3.5ff69f20.chunk.js) | challenge、Turnstile、签到、兑换、freeCap | `6af6612290a2037b87276a6bf06bfe404ed98315ccdfb6ffecba45cf9ed3d29d` |
| [GLaDOS proof](https://glados.cloud/static/js/main~4ce9bdcd.fa057b26.chunk.js) | 模块 632 的 proof 实现 | `cfbb68acc326b8dd4189a71294fb2c48f86e2db17bf1741ede0df17d147af9ed` |
| [GLaDOS HTTP 模块](https://glados.cloud/static/js/22.18205dd5.chunk.js) | JSON 请求序列化 | `016592ef5b5114e7944fa89114ef2b2c6ca3b1b8f91a121b4581d824054ca6c0` |
| [Railgun 首页](https://railgun.info/static/js/26.e5954735.chunk.js) | token-only 签到 | `aaa753fd7313ef5f9b2dc016960424df4a6b37ecc322f6d7b56d2e017640b0e2` |
| [Railgun 积分页](https://railgun.info/static/js/35.20059f05.chunk.js) | 兑换请求 | `f02e2b0adf60479842dfeb891a9a2e9b2f490e1167219022153fa2e10397e761` |
| [Railgun HTTP 模块](https://railgun.info/static/js/59.829a9035.chunk.js) | JSON 请求序列化 | `91584d10f906915b3ae74eaf97edbdd68d005d909451e52228209dea06a8f2d0` |

REA 对 GLaDOS 控制台脚本进行静态语法分析，保留父证据 ID `ev_0923912389b6e90a863943d593a9cfe5f97aa16ba7e710d2441eff985686ad25`。该分析只选取相关文件，覆盖范围有限，不代表已观察真实账号执行。

## 实现与验证

脚本对 GLaDOS 每次获取新 challenge，验证结构、nonce 和 TTL，再等待 2.7 秒，以单调时钟检查等待时长和过期状态。同一个 nonce 只提交一次，不跨域重放，不跟随重定向；下次调用重新获取验证。Railgun 按其当前独立流程发送 token。

失败、缺少验证或需要 Turnstile 时，脚本保留失败原因、跳过积分查询与兑换，并继续按账号聚合退出码。未知的 `code=1` 不再一律视为重复；保留已知的旧重复签到文案，`code=0, repeated=true` 的新格式也计为正常重复。只有成功／重复且有效积分达到阈值时才兑换。

验证直接调用当日官网原始模块 632，在受控的本地 Node 25.2.1 VM 中使用 WebCrypto 处理三组模拟 nonce，没有加载浏览器账号环境。结果与 Python 实现一致；小型测试向量保存在 `tests/fixtures/checkin-proof-vectors.json`，不包含真实 nonce 或 proof。

运行 `python -m unittest discover -s tests -v` 验证请求顺序、同域 Cookie／UA、proof 向量、TTL、过期、无效 JSON、重定向、Turnstile、重复签到、失败退出码以及失败后不兑换。所有 HTTP 请求和等待均由测试替身接管。运行环境为 Python 3.13，requests 2.32.5、pypushdeer 0.0.3；YAML 语法检查使用 PyYAML 6.0.3。这些是临时验证环境中的准确版本，本轮没有新增运行时依赖。

验证不证明某个账号下一次首次签到的奖励，也不独立确认付费后的积分效果。真实入账仍需核对该账号的官网流水。大型官网脚本、临时克隆、虚拟环境和验证用脚本在提交与 CI 验证完成后删除，只保留本记录、修复源码和模拟测试向量。
