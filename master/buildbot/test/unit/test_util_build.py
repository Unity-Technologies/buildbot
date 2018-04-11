from twisted.trial import unittest
from buildbot.util.build import add_css_classes_to_results


class TestUtilBuild(unittest.TestCase):
    def test_add_css_classes_to_results(self):
        builds = [{'results': i} for i in range(-1, 12)]
        expected_builds = [
            {'results': -1, 'result_css_class': 'running',                'result_name': 'running'},
            {'results':  0, 'result_css_class': 'success',                'result_name': 'success'},
            {'results':  1, 'result_css_class': 'warnings',               'result_name': 'warnings'},
            {'results':  2, 'result_css_class': 'failure',                'result_name': 'failure'},
            {'results':  3, 'result_css_class': 'skipped',                'result_name': 'skipped'},
            {'results':  4, 'result_css_class': 'exception',              'result_name': 'exception'},
            {'results':  5, 'result_css_class': 'retry',                  'result_name': 'retry'},
            {'results':  6, 'result_css_class': 'canceled',               'result_name': 'canceled'},
            {'results':  7, 'result_css_class': 'not-rebuilt',            'result_name': 'not-rebuilt'},
            {'results':  8, 'result_css_class': 'dependency-failure',     'result_name': 'dependency-failure'},
            {'results':  9, 'result_css_class': 'waiting-for-dependency', 'result_name': 'resume'},
            {'results': 10, 'result_css_class': 'not-started',            'result_name': 'merged'},
            {'results': 11, 'result_css_class': 'interrupted',            'result_name': 'interrupted'},
        ]

        builds_with_css = add_css_classes_to_results(builds)

        self.assertEqual(builds_with_css, expected_builds)
