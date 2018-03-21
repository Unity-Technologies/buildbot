import datetime
import json
import mock
from klog import err_json
from klog import __get_json as get_json
from twisted.python import failure
from twisted.trial import unittest


class TestKlog(unittest.TestCase):
    def check_failure(self, fail_dict, method_name):
        expected_failure = {
            'type': "<type 'exceptions.ZeroDivisionError'>",
            'value': 'integer division or modulo by zero',
            'msg': '[list of exceptions]',
            'datetime': datetime.datetime.now(),
            'method': method_name,
            'file': 'test_klog.py',
            'line': 23,
        }
        self.assertEqual(fail_dict['type'], expected_failure['type'])
        self.assertEqual(fail_dict['value'], expected_failure['value'])
        self.assertSubstring(fail_dict['msg'][0], "[")
        self.assertSubstring(fail_dict['msg'][-1], "]")
        self.assertEqual(fail_dict['method'], expected_failure['method'])
        self.assertIn(expected_failure['file'], fail_dict['file'])
        self.assertGreater(fail_dict['line'], 20)
        self.assertEqual(len(fail_dict), len(expected_failure))

    def check_exception(self, fail_dict):
        expected_failure = {
            'type': "<type 'exceptions.ZeroDivisionError'>",
            'value': 'integer division or modulo by zero',
            'msg': '[list of exceptions]',
            'datetime': datetime.datetime.now(),
        }
        self.assertEqual(fail_dict['type'], expected_failure['type'])
        self.assertEqual(fail_dict['value'], expected_failure['value'])
        self.assertSubstring(fail_dict['msg'][0], "[")
        self.assertSubstring(fail_dict['msg'][-1], "]")
        self.assertEqual(len(fail_dict), len(expected_failure))

    def test_get_json_for_failure(self):
        fail_dict = {}

        try:
            0 / 0
        except:
            fail = failure.Failure()
            fail_dict = json.loads(get_json(fail))

        self.check_failure(fail_dict, "test_get_json_for_failure")

    def test_get_json_for_exception(self):
        fail_dict = {}

        try:
            0 / 0
        except Exception as ex:
            fail = failure.Failure(ex)
            fail_dict = json.loads(get_json(fail))

        self.check_exception(fail_dict)

    @mock.patch('twisted.python.log')
    def test_err_json_for_failure(self, log):
        try:
            0 / 0
        except:
            err_json()

        fail_dict = json.loads(log.msg.call_args[0][0])

        self.check_failure(fail_dict, "test_err_json_for_failure")

    @mock.patch('twisted.python.log')
    def test_err_json_for_exception(self, log):
        try:
            0 / 0
        except Exception as ex:
            err_json(ex)

        fail_dict = json.loads(log.msg.call_args[0][0])

        self.check_exception(fail_dict)
