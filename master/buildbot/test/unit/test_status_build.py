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
from twisted.internet import defer
from zope.interface import implements
import mock
from twisted.trial import unittest
from buildbot.status import build
from buildbot import interfaces
from buildbot.test.fake import fakemaster
from buildbot.util.steps import get_steps
from buildbot.util.urls import get_url_and_name_build_in_chain
from buildbot.util import ComparableMixin, now
from buildbot.status import results
import buildbot.util.steps


class FakeBuilderStatus:
    implements(interfaces.IBuilderStatus)


class FakeSource(ComparableMixin):
    compare_attrs = ('codebase', 'revision')
    def __init__(self, codebase, revision):
        self.codebase = codebase
        self.revision = revision

    def clone(self):
        return FakeSource(self.codebase, self.revision)

    def getAbsoluteSourceStamp(self, revision):
        return FakeSource(self.codebase, revision)

    def __repr__(self):
        # note: this won't work for VC systems with huge 'revision' strings
        text = []
        if self.codebase:
            text.append("(%s)" % self.codebase)
        if self.revision is None:
            return text + [ "latest" ]
        text.append(str(self.revision))
        return "FakeSource(%s)" % (', '.join(text),)

class TestBuildProperties(unittest.TestCase):
    """
    Test that a BuildStatus has the necessary L{IProperties} methods and that
    they delegate to its C{properties} attribute properly - so really just a
    test of the L{IProperties} adapter.
    """

    BUILD_NUMBER = 33

    def setUp(self):
        self.builder_status = FakeBuilderStatus()
        self.master = fakemaster.make_master()
        self.build_status = build.BuildStatus(self.builder_status, self.master,
                                              self.BUILD_NUMBER)
        self.build_status.properties = mock.Mock()

    def customUrlTestSetup(self):
        customUrls = [{'name': 'test tool', 'link': 'test link'}]
        builderConfig = mock.Mock()
        builderConfig.getCustomBuildUrls = lambda buildbotUrl, buildNumber, buildUrl: customUrls
        self.build_status.master.status.getBuildbotURL = lambda: "http://localhost/"
        self.build_status.master.status.getURLForThing = lambda build: "http://localhost/build/%d" % build.number
        self.build_status.builder.getBuilderConfig = lambda: builderConfig
        return customUrls

    def test_getProperty(self):
        self.build_status.getProperty('x')
        self.build_status.properties.getProperty.assert_called_with('x', None)

    def test_getProperty_default(self):
        self.build_status.getProperty('x', 'nox')
        self.build_status.properties.getProperty.assert_called_with('x', 'nox')

    def test_setProperty(self):
        self.build_status.setProperty('n', 'v', 's')
        self.build_status.properties.setProperty.assert_called_with('n', 'v',
                                                            's', runtime=True)

    def test_hasProperty(self):
        self.build_status.properties.hasProperty.return_value = True
        self.assertTrue(self.build_status.hasProperty('p'))
        self.build_status.properties.hasProperty.assert_called_with('p')

    def test_render(self):
        self.build_status.render("xyz")
        self.build_status.properties.render.assert_called_with("xyz")

    def test_getCustomUrlsBuildFinished(self):
        customUrls = self.customUrlTestSetup()
        self.build_status.finished = True
        self.assertEquals(customUrls, self.build_status.getCustomUrls())

    def test_getCustomUrlsBuildRunning(self):
        self.customUrlTestSetup()
        self.build_status.finished = None
        self.assertEquals([], self.build_status.getCustomUrls())

class TestBuildGetSourcestamps(unittest.TestCase):
    """
    Test that a BuildStatus has the necessary L{IProperties} methods and that
    they delegate to its C{properties} attribute properly - so really just a
    test of the L{IProperties} adapter.
    """
    BUILD_NUMBER = 33

    def setUp(self):
        self.builder_status = FakeBuilderStatus()
        self.master = fakemaster.make_master()
        self.build_status = build.BuildStatus(self.builder_status, self.master,
                                              self.BUILD_NUMBER)

    def test_getSourceStamps_no_codebases(self):
        got_revisions = {'': '1111111'}
        self.build_status.sources = [FakeSource('', '0000000')]
        self.build_status.setProperty('got_revision', got_revisions)
        sourcestamps = [ss for ss in self.build_status.getSourceStamps(absolute=False)]
        self.assertEqual(sourcestamps, [FakeSource('', '0000000')])

    def test_getSourceStamps_no_codebases_absolute(self):
        got_revisions = {'': '1111111'}
        self.build_status.sources = [FakeSource('', '0000000')]
        self.build_status.setProperty('got_revision', got_revisions)
        sourcestamps = [ss for ss in self.build_status.getSourceStamps(absolute=True)]
        self.assertEqual(sourcestamps, [FakeSource('', '1111111')])

    def test_getSourceStamps_with_codebases_absolute(self):
        got_revisions = {'lib1': '1111111', 'lib2': 'aaaaaaa'}
        self.build_status.sources = [FakeSource('lib1', '0000000'),
                                     FakeSource('lib2', '0000000')]
        self.build_status.setProperty('got_revision', got_revisions)
        sourcestamps = [ss for ss in self.build_status.getSourceStamps(absolute=True)]
        expected_sourcestamps = [FakeSource('lib1', '1111111'),
                                 FakeSource('lib2', 'aaaaaaa')]
        self.assertEqual(sourcestamps, expected_sourcestamps)

    def test_getSourceStamps_with_codebases_less_gotrevisions_absolute(self):
        got_revisions = {'lib1': '1111111', 'lib2': 'aaaaaaa'}
        self.build_status.sources = [FakeSource('lib1', '0000000'),
                                     FakeSource('lib2', '0000000'),
                                     FakeSource('lib3', '0000000')]
        self.build_status.setProperty('got_revision', got_revisions)
        sourcestamps = [ss for ss in self.build_status.getSourceStamps(absolute=True)]
        expected_sourcestamps = [FakeSource('lib1', '1111111'),
                                 FakeSource('lib2', 'aaaaaaa'),
                                 FakeSource('lib3', '0000000')]
        self.assertEqual(sourcestamps, expected_sourcestamps)


class TestBuildStatusUtils(unittest.TestCase):
    BUILD_NUMBER = 33

    def setUp(self):
        self.builder_status = FakeBuilderStatus()
        self.master = fakemaster.make_master()
        self.build_status = build.BuildStatus(self.builder_status, self.master,
                                              self.BUILD_NUMBER)

    @mock.patch('buildbot.status.web.base.path_to_build_by_params')
    def test_get_url_and_name_build_in_chain_with_selected_build_in_chain(self, path_mock):
        path_mock.return_value = "http://example.com/example/url"

        chained_builds = [
            {'id': 1, 'buildername': 'Test Builder', 'number': 13},
            {'id': 2, 'buildername': 'Test Builder', 'number': 14},
            {'id': 3, 'buildername': 'Another Builder', 'number': 15},
            {'id': 4, 'buildername': 'Another Builder', 'number': 16},
        ]
        build_id = 3

        build_url, build_name = get_url_and_name_build_in_chain(
            build_id,
            chained_builds,
            None,
            None,
        )

        self.assertEqual(build_url, "http://example.com/example/url")
        self.assertEqual(build_name, "Another Builder #15")

    def test_get_url_and_name_build_in_chain_with_selected_build_not_in_chain(self):
        chained_builds = [
            {'id': 1, 'buildername': 'Test Builder', 'number': 13},
            {'id': 2, 'buildername': 'Test Builder', 'number': 14},
            {'id': 3, 'buildername': 'Another Builder', 'number': 15},
            {'id': 4, 'buildername': 'Another Builder', 'number': 16},
        ]
        build_id = 5

        build_url, build_name = get_url_and_name_build_in_chain(
            build_id,
            chained_builds,
            None,
            None,
        )

        self.assertEqual(build_url, None)
        self.assertEqual(build_name, None)

    def test_setUserID(self):
        self.build_status.setUserID(5)

        self.assertEqual(self.build_status.user_id, 5)

    @mock.patch("klog.err_json")
    def test_setUserID_from_owners(self, err_json):
        self.build_status.owners = ['pyflakes <pyflakes@unity3d.com>']
        self.build_status.master.db = mock.Mock()
        self.build_status.master.db.users.getUidByLdapUsername = mock.Mock(return_value=6)
        self.build_status.builder.project = "Test Project"
        self.build_status.builder.name = "Test Builder"

        self.build_status.setUserID(None)

        self.assertEqual(self.build_status.user_id, 6)
        self.assertEqual(err_json.called, True)

    @mock.patch("klog.err_json")
    def test_setUserID_unknown_owner(self, err_json):
        self.build_status.owners = ['pyflakes <pyflakes@unity3d.com>']
        self.build_status.master.db = mock.Mock()
        self.build_status.master.db.users.getUidByLdapUsername = mock.Mock(return_value=None)
        self.build_status.builder.project = "Test Project"
        self.build_status.builder.name = "Test Builder"

        self.build_status.setUserID(None)

        self.assertEqual(self.build_status.user_id, None)
        self.assertEqual(err_json.called, True)

    @mock.patch("klog.err_json")
    def test_setUserID_empty_owners(self, err_json):
        self.build_status.owners = []
        self.build_status.master.db = mock.Mock()
        self.build_status.master.db.users.getUidByLdapUsername = mock.Mock(return_value=7)
        self.build_status.builder.project = "Test Project"
        self.build_status.builder.name = "Test Builder"

        self.build_status.setUserID(None)

        self.assertEqual(self.build_status.user_id, None)
        self.assertEqual(err_json.called, True)


class BuildStepStub:
    implements(interfaces.IBuildStepStatus)

    def __init__(
            self,
            name,
            start_time,
            end_time,
            results,
            is_started,
            is_finished,
            is_hidden,
            is_waiting_for_locks,
    ):
        self.name = name
        self.start = start_time
        self.end = end_time
        self.results = results
        self.is_started = is_started
        self.is_finished = is_finished
        self.is_hidden = is_hidden
        self.is_waiting_for_locks = is_waiting_for_locks

    def getName(self):
        return self.name

    def getText(self):
        return [self.name, self.name, self.name]

    def isStarted(self):
        return self.is_started

    def isFinished(self):
        return self.is_finished

    def isHidden(self):
        return self.is_hidden

    def isWaitingForLocks(self):
        return self.is_waiting_for_locks

    def getTimes(self):
        return self.start, self.end

    def getResults(self):
        return self.results

    def prepare_trigger_links(self, codebases_arg):
        return []


class TestBuildStepsUtils(unittest.TestCase):

    @mock.patch.object(buildbot.util.steps, 'path_to_step')
    @mock.patch.object(buildbot.util.steps, '__prepare_url_object')
    @mock.patch.object(buildbot.util.steps, '__get_logs_for_step')
    @defer.inlineCallbacks
    def test_get_steps_with_unhidden_and_finished_steps_object(
            self, get_logs_mock, get_prepare_url_mock, path_to_step_mock
    ):
        path_to_step_mock.return_value = 'example-path'
        get_logs_mock.return_value = {}
        get_prepare_url_mock.return_value = {}
        start_time = now()
        expected_step1 = {
            'time_to_run': '3 mins, 20 secs',
            'name': 'Step 1',
            'css_class': 'success',
        }
        expected_step2 = {
            'time_to_run': '4 mins, 10 secs',
            'name': 'Step 2',
            'css_class': 'exception'
        }
        steps_list = [
            BuildStepStub("Step 1", start_time-100, start_time+100, [results.SUCCESS], True, True, False, False),
            BuildStepStub("Step 2", start_time-50, start_time+200, [results.EXCEPTION], True, True, False, False),
        ]

        steps = yield get_steps(steps_list, "", None)

        self.assertEqual(len(steps), 2)
        self.assertDictContainsSubset(expected_step1, steps[0])
        self.assertDictContainsSubset(expected_step2, steps[1])

    @mock.patch.object(buildbot.util.steps, 'path_to_step')
    @mock.patch.object(buildbot.util.steps, '__prepare_url_object')
    @mock.patch.object(buildbot.util.steps, '__get_logs_for_step')
    @defer.inlineCallbacks
    def test_get_steps_with_hidden_steps_object(
            self, get_logs_mock, get_prepare_url_mock, path_to_step_mock
    ):
        path_to_step_mock.return_value = 'example-path'
        get_logs_mock.return_value = {}
        get_prepare_url_mock.return_value = {}
        start_time = now()

        steps_list = [
            BuildStepStub("Step 1", start_time - 100, start_time + 100, [results.SUCCESS], True, True, True, False),
            BuildStepStub("Step 2", start_time - 50, start_time + 200, [results.EXCEPTION], True, True, True, False),
        ]

        steps = yield get_steps(steps_list, "", None)

        self.assertEqual(len(steps), 0)

    @mock.patch.object(buildbot.util.steps, 'path_to_step')
    @mock.patch.object(buildbot.util.steps, '__prepare_url_object')
    @mock.patch.object(buildbot.util.steps, '__get_logs_for_step')
    @defer.inlineCallbacks
    def test_get_steps_with_not_finished_steps_object(
            self, get_logs_mock, get_prepare_url_mock, path_to_step_mock,
    ):
        path_to_step_mock.return_value = 'example-path'
        get_logs_mock.return_value = {}
        get_prepare_url_mock.return_value = {}
        start_time = now()
        expected_step1 = {
            'time_to_run': 'running',
            'name': 'Step 1',
            'css_class': 'running',
        }
        expected_step2 = {
            'time_to_run': 'waiting for locks',
            'name': 'Step 2',
            'css_class': 'waiting',
        }

        steps_list = [
            BuildStepStub("Step 1", start_time - 100, None, [results.BEGINNING], True, False, True, False),
            BuildStepStub("Step 2", start_time - 50, None, [results.BEGINNING], True, False, True, True),
        ]

        steps = yield get_steps(steps_list, "", None)

        self.assertEqual(len(steps), 2)
        self.assertDictContainsSubset(expected_step1, steps[0])
        self.assertDictContainsSubset(expected_step2, steps[1])
