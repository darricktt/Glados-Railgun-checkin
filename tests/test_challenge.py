"""Offline protocol regression tests; every HTTP request is intercepted."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import requests

import checkin
from test_checkin import OfflineCase, USER_AGENT


class ChallengeTests(OfflineCase):
    def install_transport(self, challenge=None, checkin_body=None, points=None, status=200):
        self.sent = []
        self.challenge_body = challenge if challenge is not None else {'code': 0, 'nonce': 'synthetic-nonce', 'ttl': 300000}
        self.checkin_body = checkin_body if checkin_body is not None else {'code': 0, 'points': 2, 'message': 'Checkin! Got 2 Points'}
        self.points_body = points if points is not None else {'code': 0, 'points': 0}

        def send(session, request, **kwargs):
            self.sent.append(request)
            self.assertFalse(kwargs['allow_redirects'])
            if request.url.endswith('/challenge'):
                payload = self.challenge_body
            elif request.url.endswith('/checkin'):
                payload = self.checkin_body
            elif request.url.endswith('/points'):
                payload = self.points_body
            else:
                payload = {'code': 0, 'data': {'leftDays': 30}, 'message': 'OK'}
            response = requests.Response()
            response.status_code = status
            response._content = json.dumps(payload).encode()
            response.request = request
            return response

        return patch.object(requests.Session, 'send', send)

    def result(self):
        with checkin.API('glados.cloud', user_agent=USER_AGENT) as api:
            return api.checkin('session=account-one')

    def test_challenge_precedes_post_with_known_proof_and_same_origin(self):
        with self.install_transport():
            result = self.result()
        self.assertEqual(result['code'], checkin.CheckinStatus.SUCCESS)
        self.assertEqual([r.method for r in self.sent], ['GET', 'POST'])
        self.assertEqual([r.url for r in self.sent], [
            'https://glados.cloud/api/user/checkin/challenge',
            'https://glados.cloud/api/user/checkin',
        ])
        payload = json.loads(self.sent[1].body)
        self.assertEqual(payload, {
            'token': 'glados.cloud', 'nonce': 'synthetic-nonce',
            'proof': '95d98116667d20076de5e31eeba57cb65dac0e9be21afb32263bac1178699533',
            'tsState': 'off',
        })
        self.sleep.assert_called_once_with(2.7)
        self.assertGreaterEqual(self.now - 100, 2.5)
        for r in self.sent:
            self.assertEqual(r.headers['User-Agent'], USER_AGENT)
            self.assertEqual(r.headers['Cookie'], 'session=account-one')

    def test_vectors_from_original_official_javascript_module(self):
        vectors = json.loads((Path(__file__).parent / 'fixtures' / 'checkin-proof-vectors.json').read_text())
        for vector in vectors:
            with self.subTest(nonce=vector['nonce']):
                with self.install_transport(challenge={'code': 0, 'nonce': vector['nonce']}):
                    self.assertEqual(self.result()['code'], checkin.CheckinStatus.SUCCESS)
                    self.assertEqual(json.loads(self.sent[1].body)['proof'], vector['proof'])

    def test_missing_or_invalid_nonce_never_posts(self):
        for value in ('', 12, [], {}, 'x' * 4097, None):
            with self.subTest(value_type=type(value).__name__):
                with self.install_transport(challenge={'code': 0, 'nonce': value}):
                    self.assertEqual(self.result()['code'], checkin.CheckinStatus.FAILURE)
                    self.assertEqual(len(self.sent), 1)

    def test_invalid_ttl_never_posts(self):
        for value in (None, True, False, '300000', float('nan'), float('inf'), -1, 0, 2500, 2700):
            with self.subTest(ttl=value):
                with self.install_transport(challenge={'code': 0, 'nonce': 'test', 'ttl': value}):
                    self.assertEqual(self.result()['code'], checkin.CheckinStatus.FAILURE)
                    self.assertEqual(len(self.sent), 1)

    def test_missing_ttl_uses_official_default(self):
        with self.install_transport(challenge={'code': 0, 'nonce': 'test'}):
            self.assertEqual(self.result()['code'], checkin.CheckinStatus.SUCCESS)

    def test_expired_or_exactly_expired_challenge_never_posts(self):
        for elapsed in (3.0, 4.0):
            with self.subTest(elapsed=elapsed):
                self.now = 100
                with self.install_transport(challenge={'code': 0, 'nonce': 'test', 'ttl': 3000}), patch.object(checkin.time, 'sleep', side_effect=lambda _: setattr(self, 'now', self.now + elapsed)):
                    self.assertEqual(self.result()['code'], checkin.CheckinStatus.FAILURE)
                    self.assertEqual(len(self.sent), 1)

    def test_interrupted_wait_never_posts(self):
        with self.install_transport(), patch.object(checkin.time, 'sleep'):
            self.assertEqual(self.result()['code'], checkin.CheckinStatus.FAILURE)
            self.assertEqual(len(self.sent), 1)

    def test_turnstile_requirement_never_posts_or_sleeps(self):
        for value in ({'sitekey': 'test'}, {}, [], True, 'sitekey', 1):
            with self.subTest(metadata=value):
                with self.install_transport(challenge={'code': 0, 'nonce': 'test', 'turnstile': value}):
                    result = self.result()
                    self.assertEqual(result['code'], checkin.CheckinStatus.FAILURE)
                    self.assertIn('Turnstile', result['message'])
                    self.assertEqual(len(self.sent), 1)
        self.sleep.assert_not_called()

    def test_disabled_turnstile_metadata_matches_browser(self):
        for value in (None, False, '', 0):
            with self.subTest(metadata=value):
                with self.install_transport(challenge={'code': 0, 'nonce': 'test', 'turnstile': value}):
                    self.assertEqual(self.result()['code'], checkin.CheckinStatus.SUCCESS)

    def test_challenge_denial_or_malformed_body_does_not_fall_back(self):
        for payload in ({'code': -2}, {'code': 4, 'nonce': 'test'}, {'code': False, 'nonce': 'test'}, [], 'bad'):
            with self.subTest(payload=payload):
                with self.install_transport(challenge=payload):
                    self.assertEqual(self.result()['code'], checkin.CheckinStatus.FAILURE)
                    self.assertEqual(len(self.sent), 1)

    def test_challenge_http_failures_and_redirects_never_post(self):
        for status in (302, 401, 403, 500):
            with self.subTest(status=status):
                with self.install_transport(status=status):
                    self.assertEqual(self.result()['code'], checkin.CheckinStatus.FAILURE)
                    self.assertEqual(len(self.sent), 1)

    def test_invalid_challenge_json_never_posts(self):
        with self.install_transport(), patch.object(requests.Response, 'json', side_effect=ValueError('invalid JSON')):
            self.assertEqual(self.result()['code'], checkin.CheckinStatus.FAILURE)
            self.assertEqual(len(self.sent), 1)

    def test_post_error_is_not_replayed(self):
        with self.install_transport() as _:
            original_send = requests.Session.send
            def send(session, request, **kwargs):
                if request.method == 'POST':
                    self.sent.append(request)
                    raise requests.Timeout('test')
                return original_send(session, request, **kwargs)
            with patch.object(requests.Session, 'send', send):
                self.assertEqual(self.result()['code'], checkin.CheckinStatus.FAILURE)
            self.assertEqual([r.method for r in self.sent], ['GET', 'POST'])

    def test_each_new_attempt_fetches_fresh_nonce(self):
        with self.install_transport():
            self.result()
            self.challenge_body['nonce'] = 'a-new-synthetic-nonce'
            self.result()
        self.assertEqual([r.method for r in self.sent], ['GET', 'POST', 'GET', 'POST'])
        first, second = (json.loads(self.sent[i].body) for i in (1, 3))
        self.assertNotEqual(first['nonce'], second['nonce'])
        self.assertNotEqual(first['proof'], second['proof'])

    def test_code_zero_repeated_true_is_repeat(self):
        with self.install_transport(checkin_body={'code': 0, 'repeated': True, 'points': 14}):
            result = self.result()
        self.assertEqual(result['code'], checkin.CheckinStatus.REPEAT)
        self.assertEqual(result['points'], '0')

    def test_arbitrary_code_one_is_not_success(self):
        for repeated in (False, True):
            with self.subTest(repeated=repeated):
                with self.install_transport(checkin_body={'code': 1, 'repeated': repeated, 'message': 'challenge validation failed'}):
                    self.assertEqual(self.result()['code'], checkin.CheckinStatus.FAILURE)

    def test_bool_code_is_not_zero_and_string_repeat_is_not_true(self):
        with self.install_transport(checkin_body={'code': False, 'message': 'invalid'}):
            self.assertEqual(self.result()['code'], checkin.CheckinStatus.FAILURE)
        with self.install_transport(checkin_body={'code': 0, 'repeated': 'false', 'points': 2}):
            self.assertEqual(self.result()['code'], checkin.CheckinStatus.SUCCESS)

    def test_low_rewards_remain_successful(self):
        for points in (1, 2):
            with self.subTest(points=points):
                with self.install_transport(checkin_body={'code': 0, 'points': points}):
                    result = self.result()
                    self.assertEqual(result['code'], checkin.CheckinStatus.SUCCESS)
                    self.assertEqual(result['points'], str(points))

    def test_failure_stops_before_points_or_exchange(self):
        with self.install_transport(challenge={'code': 0, 'nonce': 'test', 'turnstile': {'sitekey': 'test'}}):
            checker = checkin.Checker(checkin.Config())
            result = checker._checkin_on_domain('session=account-one', 1, 'glados.cloud')
            checker.results.append(result)
            self.assertTrue(checker.has_failures())
            self.assertEqual(len(self.sent), 2)  # status, then challenge
            self.assertIn('Turnstile', checker.format_results()[2])

    def test_points_below_threshold_or_invalid_response_skips_exchange(self):
        for payload in ({'code': 0, 'points': 499}, {'code': -2, 'points': 1000}):
            with self.subTest(points=payload):
                with self.install_transport(points=payload):
                    checker = checkin.Checker(checkin.Config())
                    result = checker._checkin_on_domain('session=account-one', 1, 'glados.cloud')
                    self.assertFalse(any(r.url.endswith('/exchange') for r in self.sent))
                    self.assertEqual(result.points, '2')

    def test_nonce_and_proof_are_not_logged(self):
        with self.install_transport(), patch.object(checkin, 'logger') as logger:
            self.checkin_body['message'] = 'synthetic-nonce 95d98116667d20076de5e31eeba57cb65dac0e9be21afb32263bac1178699533'
            with checkin.API('glados.cloud', verbose=True) as api:
                result = api.checkin('session=account-one')
            rendered = str(logger.mock_calls) + result['message']
            self.assertNotIn('synthetic-nonce', rendered)
            self.assertNotIn('95d98116667d20076', rendered)

    def test_long_nonce_is_redacted_before_message_is_truncated(self):
        nonce = 'sensitive-synthetic-nonce-' * 30
        with self.install_transport(challenge={'code': 0, 'nonce': nonce}, checkin_body={'code': nonce, 'message': nonce}), patch.object(checkin, 'logger') as logger:
            result = self.result()
            self.assertEqual(result['code'], checkin.CheckinStatus.FAILURE)
            self.assertNotIn('sensitive-synthetic-nonce-', str(logger.mock_calls) + result['message'])


if __name__ == '__main__':
    unittest.main()
