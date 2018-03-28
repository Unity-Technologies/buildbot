import datetime
import json
import mock
from klog import err_json
from klog import __get_json as get_json
from twisted.python import failure
from twisted.trial import unittest


class TestKlog(unittest.TestCase):
    def check_failure(self, fail_dict, method_name):
        similar_to_failure = {
            'type': "<type 'exceptions.ZeroDivisionError'>",
            'value': 'integer division or modulo by zero',
            'msg': '[list of exceptions]',
            'datetime': datetime.datetime.now(),
            'method': method_name,
            'file': 'test_klog.py',
            'line': 23,
            'header': None,
            'error_hash': 'string with uuid4'
        }
        self.assertEqual(fail_dict['type'], similar_to_failure['type'])
        self.assertEqual(fail_dict['value'], similar_to_failure['value'])
        self.assertEqual(fail_dict['method'], similar_to_failure['method'])
        self.assertIn(similar_to_failure['file'], fail_dict['file'])
        self.assertIn('msg', fail_dict)
        self.assertIn('datetime', fail_dict)
        self.assertIn('line', fail_dict)
        self.assertIn('header', fail_dict)
        self.assertIn('error_hash', fail_dict)
        self.assertEqual(len(fail_dict), len(similar_to_failure))

    def check_exception(self, fail_dict):
        similar_to_failure = {
            'type': "<type 'exceptions.ZeroDivisionError'>",
            'value': 'integer division or modulo by zero',
            'msg': '[list of exceptions]',
            'datetime': datetime.datetime.now(),
            'header': None,
            'error_hash': 'string with uuid4'
        }
        self.assertEqual(fail_dict['type'], similar_to_failure['type'])
        self.assertEqual(fail_dict['value'], similar_to_failure['value'])
        self.assertIn('msg', fail_dict)
        self.assertIn('datetime', fail_dict)
        self.assertIn('header', fail_dict)
        self.assertIn('error_hash', fail_dict)
        self.assertEqual(len(fail_dict), len(similar_to_failure))

    def check_exception_with_why(self, fail_dict):
        similar_to_failure = {
            'type': "<type 'exceptions.ZeroDivisionError'>",
            'value': 'integer division or modulo by zero',
            'msg': '[list of exceptions]',
            'datetime': datetime.datetime.now(),
            'header': "Very ugly exception",
            'error_hash': 'string with uuid4'
        }
        self.assertEqual(fail_dict['type'], similar_to_failure['type'])
        self.assertEqual(fail_dict['value'], similar_to_failure['value'])
        self.assertIn('msg', fail_dict)
        self.assertIn('datetime', fail_dict)
        self.assertIn('header', fail_dict)
        self.assertIn('error_hash', fail_dict)
        self.assertEqual(fail_dict['header'], similar_to_failure['header'])
        self.assertEqual(len(fail_dict), len(similar_to_failure))

    def test_get_json_for_failure(self):
        fail_dict = {}

        try:
            0 / 0
        except:
            fail = failure.Failure()
            fail_dict = json.loads(get_json(fail, None))

        self.check_failure(fail_dict, "test_get_json_for_failure")

    def test_get_json_for_exception(self):
        fail_dict = {}

        try:
            0 / 0
        except Exception as ex:
            fail = failure.Failure(ex)
            fail_dict = json.loads(get_json(fail, None))

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

    @mock.patch('twisted.python.log')
    def test_err_json_for_exception_with_why(self, log):
        try:
            0 / 0
        except Exception as ex:
            err_json(ex, _why="Very ugly exception")

        fail_dict = json.loads(log.msg.call_args[0][0])

        self.check_exception_with_why(fail_dict)
