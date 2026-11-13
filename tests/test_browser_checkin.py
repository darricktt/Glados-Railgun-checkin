import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import browser_checkin
import checkin
from test_checkin import OfflineCase


class BrowserHelpersTests(unittest.TestCase):
    def test_cookie_parser_keeps_signed_values_and_glados_scope(self):
        cookies = browser_checkin.browser_cookies('gld:sess=abc==; gld:sess.sig=xyz;')
        self.assertEqual([c['value'] for c in cookies], ['abc==', 'xyz'])
        self.assertTrue(all(c['url'] == 'https://glados.cloud/' and c['secure'] for c in cookies))

    def test_cookie_parser_rejects_malformed_headers(self):
        for value in ('', 'session', 'bad name=value', 'session=x\r\ny'):
            with self.subTest(value=value), self.assertRaises(browser_checkin.BrowserCheckinError):
                browser_checkin.browser_cookies(value)

    def test_browser_response_redacts_credentials_and_drops_account_fields(self):
        response = SimpleNamespace(
            status=200,
            request=SimpleNamespace(post_data_json={'nonce': 'fake-nonce', 'proof': 'fake-proof', 'turnstile': 'fake-widget-token'}),
            json=lambda: {'code': 0, 'points': 2, 'email': 'private@example.invalid', 'message': 'fake-nonce fake-proof fake-widget-token'},
        )
        data = browser_checkin._response_payload(response)
        self.assertNotIn('fake-', data['message'])
        self.assertNotIn('email', data)
        self.assertEqual(data['points'], 2)

    def test_browser_response_requires_business_json_and_http_success(self):
        for status, body in ((403, {}), (200, [])):
            response = SimpleNamespace(status=status, json=lambda: body)
            with self.subTest(status=status), self.assertRaises(browser_checkin.BrowserCheckinError):
                browser_checkin._response_payload(response)


class BrowserDispatchTests(OfflineCase):
    def test_browser_mode_does_not_use_http_checkin(self):
        os.environ['GLADOS_CHECKIN_MODE'] = 'browser'
        payload = {'code': 0, 'points': 2, 'message': 'Checkin! Got 2 Points'}
        captured = []
        with self.fake_transport(captured=captured), patch.object(browser_checkin, 'run_browser_checkin', return_value=(payload, 'session=refreshed')) as run:
            result = checkin.Checker(checkin.Config())._checkin_on_domain('session=account-one', 1, 'glados.cloud')
        self.assertEqual(result.code, checkin.CheckinStatus.SUCCESS)
        self.assertEqual(result.points, '2')
        run.assert_called_once()
        self.assertFalse(any('/checkin' in r.url for r in captured))
        self.assertEqual(captured[-1].headers['Cookie'], 'session=refreshed')

    def test_browser_failure_does_not_fall_back_to_http_or_exchange(self):
        os.environ['GLADOS_CHECKIN_MODE'] = 'browser'
        captured = []
        with self.fake_transport(captured=captured), patch.object(browser_checkin, 'run_browser_checkin', side_effect=browser_checkin.BrowserCheckinError('需要浏览器验证')):
            checker = checkin.Checker(checkin.Config())
            checker.checkin_all()
        self.assertTrue(checker.has_failures())
        self.assertIn('需要浏览器验证', checker.format_results()[2])
        self.assertFalse(any('/checkin' in r.url or '/exchange' in r.url for r in captured))

    def test_verification_mode_skips_exchange_and_push(self):
        os.environ['GLADOS_VERIFY_ONLY'] = 'true'
        captured = []
        with self.fake_transport(captured=captured), patch.object(checkin.PushService, 'send') as push:
            self.assertEqual(checkin.main(), 0)
        self.assertFalse(any('/exchange' in r.url for r in captured))
        push.assert_not_called()

    def test_invalid_mode_fails_without_network(self):
        os.environ['GLADOS_CHECKIN_MODE'] = 'unknown'
        self.assertEqual(checkin.main(), 1)


@unittest.skipUnless(os.environ.get('GLADOS_RUN_BROWSER_TESTS') == '1', 'Set GLADOS_RUN_BROWSER_TESTS=1 for isolated Chromium fixture tests')
class ChromiumFixtureTests(unittest.TestCase):
    """Run the real browser against intercepted fixtures; no live site calls."""
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def fixture(self, body=None, status_code=0):
        context = self.browser.new_context()
        self.addCleanup(context.close)
        context.add_cookies(browser_checkin.browser_cookies('gld:sess=synthetic-account'))
        observed = []
        result = body if body is not None else {'code': 0, 'points': 2, 'message': 'Checkin! Got 2 Points'}
        html = """<button onclick="fetch('/api/user/checkin',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:'glados.cloud'})}).then(r=>r.json())">Checkin</button>"""
        def route(request_route):
            request = request_route.request
            observed.append((request.method, request.url))
            if request.url == 'https://glados.cloud/console/checkin':
                request_route.fulfill(status=200, content_type='text/html', body=html)
            elif request.url == 'https://glados.cloud/api/user/status':
                request_route.fulfill(status=200, content_type='application/json', body=json.dumps({'code': status_code}))
            elif request.url == browser_checkin.CHECKIN_URL:
                request_route.fulfill(status=200, content_type='application/json', body=json.dumps(result))
            else:
                request_route.abort()
        context.route('**/*', route)
        return context, observed

    def test_browser_clicks_only_signin_and_reads_server_result(self):
        context, observed = self.fixture()
        payload, cookie = browser_checkin._checkin_in_context(context, headless=True, timeout_ms=3000, notify=lambda _: None)
        self.assertEqual(payload['code'], 0)
        self.assertEqual(payload['points'], 2)
        self.assertIn('gld:sess=synthetic-account', cookie)
        self.assertEqual([method for method, url in observed if url == browser_checkin.CHECKIN_URL], ['POST'])
        self.assertFalse(any('railgun' in url or '/exchange' in url for _, url in observed))

    def test_invalid_session_does_not_click_signin(self):
        context, observed = self.fixture(status_code=-2)
        with self.assertRaisesRegex(browser_checkin.BrowserCheckinError, '会话未通过认证'):
            browser_checkin._checkin_in_context(context, headless=True, timeout_ms=3000, notify=lambda _: None)
        self.assertFalse(any(method == 'POST' for method, _ in observed))

    def test_headless_turnstile_rejection_returns_manual_action(self):
        context, observed = self.fixture(body={'code': 4, 'reason': 'turnstile', 'message': 'Verification required'})
        with self.assertRaisesRegex(browser_checkin.BrowserCheckinError, '验证'):
            browser_checkin._checkin_in_context(context, headless=True, timeout_ms=3000, notify=lambda _: None)
        self.assertEqual(sum(method == 'POST' for method, _ in observed), 1)


if __name__ == '__main__':
    unittest.main()
