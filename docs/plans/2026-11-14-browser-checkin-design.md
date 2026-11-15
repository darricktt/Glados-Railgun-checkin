# GLaDOS 浏览器签到与单站点运行

用户要求屏蔽 Railgun，并继续推进 GLaDOS 的 Turnstile 问题。本轮将默认域名限定为 `glados.cloud`，同时拒绝为其他域名创建 API 实例。

默认路径使用标准 Playwright Chromium，导入用户已有的 GLaDOS Cookie 与登录 UA，打开官网 `/console/checkin`。脚本先检查浏览器内的会话，再唯一定位并点击 `Checkin` 按钮，监听同源 `/api/user/checkin` 的 POST 响应。官网页面自行加载并执行真实的 Turnstile 组件；脚本不修改网站验证状态、浏览器自动化标记或设备信息，不点击验证 iframe，也不调用第三方解题服务。

相比继续补充纯 HTTP 参数，浏览器路径具备执行官网验证组件的环境。相比直接改成本机定时任务，保留 GitHub Actions 可继续验证现有部署；无感验证仍由服务端决定是否接受，不能保证云端通过。需要交互时，可使用本机可见浏览器，在两分钟窗口内按官网提示操作。

浏览器响应复用现有成功／重复／失败判定，失败不回退 HTTP、不兑换。成功后仅将 GLaDOS 的 Cookie 更新用于后续积分查询和兑换，不保留浏览器状态文件或原始请求记录。`GLADOS_VERIFY_ONLY` 用于真实签到验证，跳过兑换和推送，避免测试消耗积分或发送通知。

固定依赖声明为 `requirements.txt`，完整运行依赖锁定到 `requirements.lock`。本地环境临时安装 Python 3.13、Playwright 1.65.1 及其 Chromium 1254；完成后删除临时克隆、虚拟环境和下载的浏览器。GitHub 仍使用已有的离线测试 workflow，并新增真实 Chromium 模拟页面测试，所有网络请求在测试中拦截。

验证覆盖单站点、Cookie 值与域名作用域、官网按钮定位、业务结果解析、敏感字段脱敏、失效会话、Turnstile 拒绝、失败不降级及仅验证模式。一次云端仅验证运行用于观察当前账号是否能通过真实官网验证；该结果与离线测试结论分开记录，不保证未来规则不变。

## 真实运行记录

提交 `1d74105fd4d7587209c9b41abb370d0ab8561ee0` 的[云端仅验证运行](https://github.com/darricktt/Glados-Railgun-checkin/actions/runs/43471521375)使用浏览器模式，只访问 GLaDOS，约 93 秒后收到 `code=1` 以及 `Today's observation logged. Return tomorrow for more points.`。初版解析器未识别该精确文案，因此错误返回失败；后续将这条实际观察到的响应归类为正常重复，并增加 API 与真实浏览器模拟页面回归用例。

该运行没有兑换或发送推送。重复签到响应不能证明下一次首次签到一定通过 Turnstile，也不能证明新增积分；需继续观察既有定时任务的首次签到结果，不能把本次记录描述为验证已绕过或首次签到验收完成。

2026 年 11 月 15 日，文案修复后的 `0d6a55320983b1c3f0e4bb8efc9e7bc32367aaa8` 通过[51 项云端离线测试](https://github.com/darricktt/Glados-Railgun-checkin/actions/runs/43690206748)，其中包含实际 Chromium 的模拟页面用例。[再次真实仅验证运行](https://github.com/darricktt/Glados-Railgun-checkin/actions/runs/43690231691)只执行一个 GLaDOS 任务，约 93 秒后被官网 Turnstile 验证拒绝；脚本正确返回失败，没有兑换或发送推送。因此浏览器路径已经具备正常执行官网流程的能力，但云端无人值守签到尚未通过真实验收。后续需要在本机可见浏览器完成实际交互验证，不能把离线测试通过或此前的重复签到当作替代证据。
