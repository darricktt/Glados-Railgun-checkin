"""Use the site's UI and real browser verification; never manufacture tokens."""
import re
import time
from urllib.parse import urlsplit

ORIGIN = "https://glados.cloud"
CHECKIN_URL = ORIGIN + "/api/user/checkin"
BUTTON_NAME = re.compile(r"^(check\s*in|签到|簽到|立即签到)$", re.I)


class BrowserCheckinError(RuntimeError):
    pass


def browser_cookies(header):
    cookies = []
    for entry in header.split(";"):
        entry = entry.strip()
        if not entry:
            continue
        name, separator, value = entry.partition("=")
        if not separator or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z:\-]+", name) or any(ord(c) < 32 for c in value):
            raise BrowserCheckinError("Cookie 格式无效，请复制完整的请求 Cookie 值")
        cookies.append({"name": name, "value": value, "url": ORIGIN + "/", "secure": True, "sameSite": "Lax"})
    if not cookies:
        raise BrowserCheckinError("未配置 Cookie")
    return cookies


def _response_payload(response):
    if response.status != 200:
        raise BrowserCheckinError(f"浏览器签到请求失败，HTTP {response.status}")
    try:
        body = response.json()
    except Exception:
        raise BrowserCheckinError("浏览器签到返回了无效 JSON") from None
    if not isinstance(body, dict):
        raise BrowserCheckinError("浏览器签到响应格式无效")
    message = str(body.get("message", "无消息字段"))
    request_data = response.request.post_data_json
    if isinstance(request_data, dict):
        for field in ("nonce", "proof", "turnstile"):
            secret = request_data.get(field)
            if isinstance(secret, str) and secret:
                message = message.replace(secret, "[redacted]")
    # Return only business fields; do not retain challenge bodies, account data,
    # browser traces, screenshots, or request headers.
    return {"code": body.get("code"), "points": body.get("points", 0),
            "repeated": body.get("repeated"), "reason": body.get("reason"), "message": message[:500]}


def _checkin_in_context(context, *, headless, timeout_ms, notify):
    page = context.new_page()
    page.set_default_timeout(min(timeout_ms, 30000))
    page.goto(ORIGIN + "/console/checkin", wait_until="domcontentloaded", timeout=min(timeout_ms, 30000))
    if urlsplit(page.url).hostname != "glados.cloud":
        raise BrowserCheckinError("浏览器离开了 GLaDOS，请检查登录会话")
    status = page.evaluate("""async () => {
        const r = await fetch('/api/user/status', {credentials: 'same-origin', signal: AbortSignal.timeout(15000)});
        if (r.status !== 200) return {http: r.status};
        const b = await r.json(); return {http: r.status, code: b.code};
    }""")
    if status.get("http") != 200:
        raise BrowserCheckinError("官网状态接口未通过访问验证；请先在本机浏览器确认官网能够正常打开")
    if type(status.get("code")) is not int or status["code"] != 0:
        raise BrowserCheckinError("浏览器登录会话未通过认证，请更新 GLaDOS Cookie 和登录时的 UA")

    button = page.get_by_role("button", name=BUTTON_NAME)
    button.first.wait_for(state="visible")
    if button.count() != 1:
        raise BrowserCheckinError("无法唯一定位官网签到按钮，停止操作")

    observed = []
    def receive(response):
        if response.url == CHECKIN_URL and response.request.method == "POST":
            try:
                observed.append(_response_payload(response))
            except BrowserCheckinError as error:
                observed.append(error)
            except Exception:
                observed.append(BrowserCheckinError("无法读取浏览器签到响应"))
    page.on("response", receive)
    if not headless:
        notify("浏览器已打开；如官网出现验证，请在窗口中完成。等待时间有限，不会自动点击验证组件。")
    deadline = time.monotonic() + timeout_ms / 1000
    button.click()
    while time.monotonic() < deadline:
        if observed:
            result = observed.pop(0)
            if isinstance(result, BrowserCheckinError):
                raise result
            if result.get("reason") == "turnstile":
                if headless:
                    raise BrowserCheckinError("官网未接受浏览器验证；可使用本机可见浏览器完成验证，云端无法人工接手")
                notify("官网验证尚未通过，请在浏览器中按官网提示完成并重试签到。")
            else:
                updated = "; ".join(f"{c['name']}={c['value']}" for c in context.cookies(ORIGIN))
                return result, updated
        page.wait_for_timeout(200)
    raise BrowserCheckinError("浏览器签到等待超时；可能需要交互验证，请在本机可见浏览器完成签到")


def run_browser_checkin(cookie, user_agent, *, headless=True, timeout_ms=120000, notify=lambda message: None):
    try:
        from playwright.sync_api import sync_playwright, Error
    except ImportError:
        raise BrowserCheckinError("请先安装 requirements.txt 并运行 python -m playwright install chromium") from None
    parsed = browser_cookies(cookie)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=headless)
            try:
                context = browser.new_context(user_agent=user_agent, locale="en-US")
                try:
                    context.add_cookies(parsed)
                    return _checkin_in_context(context, headless=headless, timeout_ms=timeout_ms, notify=notify)
                finally:
                    context.close()
            finally:
                browser.close()
    except Error as error:
        # Playwright diagnostics can include request contents. Keep them out of
        # public Actions logs and show only the failure category.
        raise BrowserCheckinError(f"浏览器流程中断（{type(error).__name__}）；请检查浏览器安装、登录状态和官网验证") from None
