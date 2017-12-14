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

from zope.interface import implements
import mock
from twisted.internet import defer
from twisted.trial import unittest
from buildbot.status import build
from buildbot import interfaces
from buildbot.test.fake import fakemaster
from buildbot import util

class FakeBuilderStatus:
    implements(interfaces.IBuilderStatus)

class FakeSource(util.ComparableMixin):
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


class TestBuildGetTopBuildUrl(unittest.TestCase):
    BUILD_NUMBER = 20

    def setUp(self):
        self.builder_status = FakeBuilderStatus()
        self.master = fakemaster.make_master(wantDb=True, testcase='Tests for getTopBuildUrl method')
        self.build_status = build.BuildStatus(self.builder_status, self.master, self.BUILD_NUMBER)

        def generate_build_url(buildername, build_number):
            return 'http://katana/projects/test-project/builders/{}/builds/{}'.format(buildername, build_number)

        self.master.status.getBuildersPath = mock.Mock(side_effect=generate_build_url)

    @defer.inlineCallbacks
    def test_getTopBuildUrl_codebases_arg(self):
        self.builder_status.name = 'child-builder'

        query_result = {'buildername': 'parent-builder', 'build_number': 12}
        self.master.db.buildrequests.getTopBuildData = mock.Mock(return_value=defer.succeed(query_result))
        
        top_build_url = yield self.build_status.getTopBuildUrl('?test-repository_branch=master')

        assert top_build_url == (
            'http://katana/projects/test-project/builders/parent-builder/builds/12?test-repository_branch=master'
        )

    @defer.inlineCallbacks
    def test_getTopBuildUrl_check_if_build_is_top_build(self):
        self.builder_status.name = 'parent-builder'
        self.build_status.number = 12

        query_result = {'buildername': 'parent-builder', 'build_number': 12}
        self.master.db.buildrequests.getTopBuildData = mock.Mock(return_value=defer.succeed(query_result))

        top_build_url = yield self.build_status.getTopBuildUrl('?test-repository_branch=master')

        assert top_build_url is None
        assert self.master.status.getBuildersPath.called is False

    @defer.inlineCallbacks
    def test_getTopBuildUrl_buildChainID_is_none(self):
        self.master.db.buildrequests.getTopBuildData = mock.Mock(return_value=defer.succeed({}))

        top_build_url = yield self.build_status.getTopBuildUrl('?test-repository_branch=master')

        assert top_build_url is None
        assert self.master.status.getBuildersPath.called is False
