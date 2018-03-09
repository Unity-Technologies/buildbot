# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

import mock
from buildbot.status.web import base
from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.fake.web import FakeRequest

class ActionResource(unittest.TestCase):

    def test_ActionResource_success(self):

        class MyActionResource(base.ActionResource):
            def performAction(self, request):
                self.got_request = request
                return defer.succeed('http://buildbot.net')

        rsrc = MyActionResource()
        request = FakeRequest()
        rsrc.render(request)
        d = request.deferred

        def check(_):
            self.assertIdentical(rsrc.got_request, request)
            self.assertTrue(request.finished)
            self.assertIn('buildbot.net', request.written)
            self.assertEqual(request.redirected_to, 'http://buildbot.net')
        d.addCallback(check)
        return d

    def test_ActionResource_exception(self):

        class MyActionResource(base.ActionResource):
            def performAction(self, request):
                return defer.fail(RuntimeError('sacrebleu'))

        rsrc = MyActionResource()
        request = FakeRequest()
        rsrc.render(request)
        d = request.deferred

        def check(f):
            f.trap(RuntimeError)
            # pass - all good!
        d.addErrback(check)
        return d

class Functions(unittest.TestCase):

    ### getRequestCharset ###

    def do_test_getRequestCharset(self, hdr, exp):
        req = mock.Mock()
        req.getHeader.return_value = hdr

        self.assertEqual(base.getRequestCharset(req), exp)

    def test_getRequestCharset_empty(self):
        return self.do_test_getRequestCharset(None, 'utf-8')

    def test_getRequestCharset_specified(self):
        return self.do_test_getRequestCharset(
            'application/x-www-form-urlencoded ; charset=ISO-8859-1',
            'ISO-8859-1')

    def test_getRequestCharset_other_params(self):
        return self.do_test_getRequestCharset(
            'application/x-www-form-urlencoded ; charset=UTF-16 ; foo=bar',
            'UTF-16')


    ### filter_tags_by_codebases ###

    def test_filter_tags_by_codebases_many_tags(self):
        tags = ['Unstable', 'Trunk', 'Trunk-ABV', 'Trunk-Unstable', '2018.2', '2018.2-QV']
        codebases = {'unity': '2018.2/'}
        expected_tags = ['QV', 'Unstable']

        filtered_tags = base.filter_tags_by_codebases(tags, codebases)

        self.assertEqual(expected_tags, filtered_tags)

    def test_filter_tags_by_codebases_many_cb(self):
        tags = ['Unstable', 'Trunk', 'Trunk-ABV', 'Trunk-Unstable', '2018.2', '2018.2-QV']
        codebases = {'unity': 'trunk/', 'mod': '2018.2/'}
        expected_tags = ['ABV', 'QV', 'Unstable']

        filtered_tags = base.filter_tags_by_codebases(tags, codebases)

        self.assertEqual(expected_tags, filtered_tags)

    def test_filter_tags_by_codebases_simple_unstable(self):
        tags = ['Unstable', 'Trunk', 'Trunk-ABV', '2018.2', '2018.2-QV']
        codebases = {'unity': 'trunk/'}
        expected_tags = ['ABV', 'Unstable']

        filtered_tags = base.filter_tags_by_codebases(tags, codebases)

        self.assertEqual(expected_tags, filtered_tags)

    def test_filter_tags_by_codebases_foreign_unstable(self):
        tags = ['Trunk', 'Trunk-ABV', '2018.2', '2018.2-QV', '2018.2-QV-Unstable']
        codebases = {'unity': 'trunk/'}
        expected_tags = ['ABV']

        filtered_tags = base.filter_tags_by_codebases(tags, codebases)

        self.assertEqual(expected_tags, filtered_tags)

    def test_filter_tags_by_codebases_empty_cb(self):
        tags = ['Unstable', 'Trunk', 'Trunk-ABV', 'Trunk-Unstable', '2018.2', '2018.2-QV']
        codebases = {}
        expected_tags = sorted(tags)

        filtered_tags = base.filter_tags_by_codebases(tags, codebases)

        self.assertEqual(expected_tags, filtered_tags)

    def test_filter_tags_by_codebases_uknown_branch(self):
        tags = ['Unstable', 'Trunk', 'Trunk-ABV', 'Trunk-Unstable', '2018.2', '2018.2-QV']
        codebases = {'foo': '2019.2/'}       # not unity, good pattern
        expected_tags = ['ABV', 'Unstable']  # use Trunk tags

        filtered_tags = base.filter_tags_by_codebases(tags, codebases)

        self.assertEqual(expected_tags, filtered_tags)

    def test_filter_tags_by_codebases_unity_cb(self):
        tags = ['Unstable', 'Trunk', 'Trunk-ABV', 'Trunk-Unstable', '2018.2', '2018.2-QV']
        codebases = {'unity': 'zupa/'}       # unity, wrong pattern
        expected_tags = ['ABV', 'Unstable']  # use Trunk tags

        filtered_tags = base.filter_tags_by_codebases(tags, codebases)

        self.assertEqual(expected_tags, filtered_tags)

    def test_filter_tags_by_codebases_wrong_cb_and_branch(self):
        tags = ['Unstable', 'Trunk', 'Trunk-ABV', 'Trunk-Unstable', '2018.2', '2018.2-QV']
        codebases = {'foo': 'zupa/'}         # not unity, wrong pattern
        expected_tags = sorted(tags)         # return original tags

        filtered_tags = base.filter_tags_by_codebases(tags, codebases)

        self.assertEqual(expected_tags, filtered_tags)


    ### get_query_branches_for_codebases ###

    def test_get_query_branches_for_codebases_good_case(self):
        tags = ['Trunk', 'Trunk-ABV', '2018.2', '2018.2-QV']
        codebases = {'foo': '2018.2/'}
        expected_branches = {'2018.2'}

        branches = base.get_query_branches_for_codebases(tags, codebases)

        self.assertEqual(branches, expected_branches)

    def test_get_query_branches_for_codebases_unity_key(self):
        tags = ['Trunk', 'Trunk-ABV', '2018.2', '2018.2-QV']
        codebases = {'unity': 'bar/'}
        expected_branches = {'trunk'}

        branches = base.get_query_branches_for_codebases(tags, codebases)

        self.assertEqual(branches, expected_branches)

    def test_get_query_branches_for_codebases_wrong_codebase(self):
        tags = ['Trunk', 'Trunk-ABV', '2018.2', '2018.2-QV']
        codebases = {'foo': 'bar/'}
        expected_branches = set()

        branches = base.get_query_branches_for_codebases(tags, codebases)

        self.assertEqual(branches, expected_branches)

    def test_get_query_branches_for_codebases_not_tags(self):
        tags = ['Trunk', 'Trunk-ABV', '2018.2', '2018.2-QV']
        codebases = {'foo': '2019.2/'}
        expected_branches = {'trunk'}

        branches = base.get_query_branches_for_codebases(tags, codebases)

        self.assertEqual(branches, expected_branches)


class TestGetResultsArg(unittest.TestCase):
    def setUpRequest(self, results=None):
        args = {}
        if results is not None:
            args["results"] = results

        request = mock.Mock()
        request.args = args

        return request

    def test_no_results_arg(self):
        self.assertIsNone(base.getResultsArg(self.setUpRequest()))

    def test_one_args(self):
        res = base.getResultsArg(self.setUpRequest(["0"]))
        self.assertEqual(res, [0])

    def test_many_args(self):
        res = base.getResultsArg(self.setUpRequest(["5", "8"]))
        self.assertEqual(res, [5, 8])

    def test_invalid_args(self):
        self.assertIsNone(base.getResultsArg(self.setUpRequest(["0",
                                                                "invalid"])))


class TestPath_to_json_past_builds(unittest.TestCase):
    def setUp(self):
        self.request = mock.Mock()
        self.request.args = {}

    def test_minimal(self):
        self.assertEqual("json/builders/bldr/builds/<43?",
                         base.path_to_json_past_builds(self.request, "bldr", 43))

    def test_all_args(self):
        self.request.args = dict(numbuilds=[10],
                                 results=[0, 7],
                                 foo=["bar"])

        url = base.path_to_json_past_builds(self.request, "bldr", 10).split('?')
        exp_args = ["foo=bar", "results=0", "results=7"]

        self.assertEqual(len(url), 2)
        self.assertTrue("json/builders/bldr/builds/<10" in url[0])
        self.assertTrue(all(arg in url[1] for arg in exp_args))

