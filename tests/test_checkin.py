import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import requests

import checkin


USER_AGENT = 'Mozilla/5.0 TestBrowser/140.0'
ROOT = Path(__file__).resolve().parents[1]


class CheckinTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            'GLADOS_COOKIES': 'session=account-one',
            'GLADOS_USER_AGENT': USER_AGENT,
        }, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.logs = patch.object(checkin, 'logger')
        self.logs.start()
        self.addCleanup(self.logs.stop)
        # Any test that needs HTTP must explicitly install a fake transport.
        self.network = patch.object(requests.Session, 'send', side_effect=AssertionError('Unexpected HTTP request'))
        self.network.start()
        self.addCleanup(self.network.stop)

    def fake_transport(self, codes=None, captured=None):
        codes = codes or {}

        def send(session, request, **kwargs):
            if captured is not None:
                captured.append(request)
            if request.url.endswith('/checkin'):
                code = codes.get((request.headers['Cookie'], request.url.split('/')[2]), 0)
                payload = {'code': code, 'message': 'Automated check-in detected. Please sign in again to continue.' if code == 4 else 'test result', 'points': 1}
            elif request.url.endswith('/status'):
                payload = {'code': 0, 'data': {'leftDays': 30}}
            elif request.url.endswith('/points'):
                payload = {'code': 0, 'points': 0}
            else:
                payload = {'code': 0, 'message': 'test exchange'}
            response = requests.Response()
            response.status_code = 200
            response._content = json.dumps(payload).encode()
            response.request = request
            return response

        return patch.object(requests.Session, 'send', send)

    def run_main(self, codes=None):
        with self.fake_transport(codes), patch.object(checkin.PushService, 'send', return_value=False):
            return checkin.main()

    def test_config_uses_trimmed_user_agent(self):
        os.environ['GLADOS_USER_AGENT'] = '  ' + USER_AGENT + '  '
        self.assertEqual(checkin.Config().user_agent, USER_AGENT)

    def test_missing_or_blank_user_agent_preserves_default(self):
        for value in (None, '', '   '):
            with self.subTest(value=value):
                if value is None:
                    os.environ.pop('GLADOS_USER_AGENT', None)
                else:
                    os.environ['GLADOS_USER_AGENT'] = value
                self.assertEqual(checkin.Config().user_agent, checkin.Config.DEFAULT_USER_AGENT)

    def test_headers_and_json_reach_prepared_requests_on_both_domains(self):
        captured = []
        with self.fake_transport(captured=captured):
            checker = checkin.Checker(checkin.Config())
            checker.checkin_all()
        self.assertEqual(len(captured), 8)
        for request in captured:
            self.assertEqual(request.headers['User-Agent'], USER_AGENT)
            self.assertEqual(request.headers['Cookie'], 'session=account-one')
            self.assertEqual(request.headers['Origin'], 'https://' + request.url.split('/')[2])
            if request.method == 'POST':
                self.assertEqual(request.headers['Content-Type'], 'application/json')
                expected = {'token': request.url.split('/')[2]} if request.url.endswith('/checkin') else {'planType': 'plan500'}
                self.assertEqual(json.loads(request.body), expected)

    def test_success_returns_zero(self):
        self.assertEqual(self.run_main(), 0)

    def test_repeat_returns_zero(self):
        codes = {('session=account-one', domain): 1 for domain in checkin.Config.DOMAINS}
        self.assertEqual(self.run_main(codes), 0)

    def test_business_failure_with_http_200_returns_one(self):
        codes = {('session=account-one', domain): 4 for domain in checkin.Config.DOMAINS}
        self.assertEqual(self.run_main(codes), 1)

    def test_one_accepted_domain_is_enough_for_a_cookie(self):
        for accepted in checkin.Config.DOMAINS:
            with self.subTest(accepted=accepted):
                codes = {('session=account-one', domain): -2 for domain in checkin.Config.DOMAINS if domain != accepted}
                self.assertEqual(self.run_main(codes), 0)

    def test_each_cookie_must_have_an_accepted_domain(self):
        os.environ['GLADOS_COOKIES'] += '&session=account-two'
        codes = {('session=account-two', domain): 4 for domain in checkin.Config.DOMAINS}
        self.assertEqual(self.run_main(codes), 1)

    def test_accounts_can_succeed_on_different_domains(self):
        os.environ['GLADOS_COOKIES'] += '&session=account-two'
        codes = {
            ('session=account-one', 'railgun.info'): -2,
            ('session=account-two', 'glados.cloud'): -2,
        }
        self.assertEqual(self.run_main(codes), 0)

    def test_missing_cookies_returns_one(self):
        os.environ.pop('GLADOS_COOKIES')
        self.assertEqual(self.run_main(), 1)

    def test_network_error_returns_one(self):
        with patch.object(requests.Session, 'send', side_effect=requests.Timeout('test timeout')):
            self.assertEqual(checkin.main(), 1)

    def test_configuration_error_returns_one(self):
        with patch.object(checkin, 'Config', side_effect=ValueError('bad config')):
            self.assertEqual(checkin.main(), 1)

    def test_error_after_success_still_returns_one(self):
        with self.fake_transport(), patch.object(checkin.Checker, 'format_results', side_effect=ValueError('bad format')):
            self.assertEqual(checkin.main(), 1)

    def test_push_runs_before_failure_is_reported(self):
        codes = {('session=account-one', domain): 4 for domain in checkin.Config.DOMAINS}
        with self.fake_transport(codes), patch.object(checkin.PushService, 'send', return_value=True) as push:
            self.assertEqual(checkin.main(), 1)
            push.assert_called_once()

    def test_cli_exits_nonzero_without_cookies(self):
        env = {key: value for key, value in os.environ.items() if not key.startswith(('GLADOS_', 'PUSHDEER_'))}
        result = subprocess.run([sys.executable, str(ROOT / 'checkin.py')], cwd=ROOT, env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('未找到有效的 Cookie', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
