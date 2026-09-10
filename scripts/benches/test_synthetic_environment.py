import json
import re
import unittest
from unittest.mock import Mock

from scripts.benches.synthetic_environment import verify_http_target


class TargetBindingTests(unittest.TestCase):
    def environment(self):
        env = Mock()
        env.run_backend_python.side_effect = [json.dumps({'user_id': 17, 'token': 'temporary'}), json.dumps({'removed': True})]
        return env

    def test_different_loopback_database_cannot_pass(self):
        env = self.environment()
        get = Mock(return_value=Mock(status_code=200, json=lambda: {'id':17, 'email':'different@example.test'}))
        self.assertFalse(verify_http_target(env, 'http://127.0.0.1:18000', get=get))
        self.assertEqual(env.run_backend_python.call_count, 2)
        self.assertFalse(get.call_args.kwargs['follow_redirects'])
        self.assertFalse(get.call_args.kwargs['trust_env'])

    def test_same_backend_passes_and_probe_is_removed(self):
        env = self.environment()
        def get(*args, **kwargs):
            source = env.run_backend_python.call_args.args[0]
            email = re.search(r'conversation-bench-probe-[a-f0-9]+@example.test', source).group()
            return Mock(status_code=200, json=lambda: {'id':17, 'email':email})
        self.assertTrue(verify_http_target(env, 'http://127.0.0.1:18000', get=get))
        self.assertIn('DELETE FROM users', env.run_backend_python.call_args.args[0])

    def test_transport_error_still_removes_probe(self):
        env = self.environment()
        self.assertFalse(verify_http_target(env, 'http://localhost:18000', get=Mock(side_effect=RuntimeError('private body'))))
        self.assertEqual(env.run_backend_python.call_count, 2)

    def test_unverified_cleanup_cannot_pass(self):
        env = self.environment()
        env.run_backend_python.side_effect = [json.dumps({'user_id':17,'token':'temporary'}), RuntimeError('cleanup failed')]
        self.assertFalse(verify_http_target(env, 'http://localhost:18000', get=Mock(return_value=Mock(status_code=401))))
