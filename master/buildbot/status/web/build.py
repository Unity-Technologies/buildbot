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
import json
from itertools import ifilter

from twisted.web import html
from twisted.internet import defer, reactor
from twisted.web.util import Redirect, DeferredResource

import time
from twisted.python import log
from buildbot.status.web.base import HtmlResource, \
    css_classes, path_to_build, path_to_builder, path_to_slave, \
    path_to_codebases, path_to_builders, getCodebasesArg, \
    ActionResource, path_to_authzfail, \
    getRequestCharset, path_to_json_build
from buildbot.schedulers.forcesched import ForceScheduler, TextParameter
from buildbot.status.web.step import StepsResource
from buildbot.status.web.tests import TestsResource
from buildbot import util, interfaces
from buildbot.util.steps import get_steps
from buildbot.status.results import RESUME
from buildbot.util.urls import get_url_and_name_build_in_chain


class CancelBuildActionResource(ActionResource):
    def __init__(self, build_status):
        self.build_status = build_status
        self.action = "stopBuild"

    @defer.inlineCallbacks
    def performAction(self, req):
        authz = self.getAuthz(req)
        res = yield authz.actionAllowed(self.action, req, self.build_status)

        if not res:
            defer.returnValue(path_to_authzfail(req))
            return

        b = self.build_status
        log.msg("web cancel of build %s:%s" % \
                    (b.getBuilder().getName(), b.getNumber()))
        name = authz.getUsernameFull(req)
        comments = req.args.get("comments", ["<no reason specified>"])[0]
        comments.decode(getRequestCharset(req))
        # html-quote both the username and comments, just to be safe
        reason = ("The web-page 'Cancel Build' button was pressed by "
                  "'%s': %s\n" % (html.escape(name), html.escape(comments)))

        if self.build_status.getResults() == RESUME:
            yield self.build_status.builder.cancelBuildRequestsOnResume(self.build_status.getNumber())

        defer.returnValue(path_to_build(req, self.build_status))


class StopBuildActionResource(ActionResource):

    def __init__(self, build_status):
        self.build_status = build_status
        self.action = "stopBuild"

    @defer.inlineCallbacks
    def performAction(self, req):
        authz = self.getAuthz(req)
        res = yield authz.actionAllowed(self.action, req, self.build_status)

        if not res:
            defer.returnValue(path_to_authzfail(req))
            return

        b = self.build_status
        log.msg("web stopBuild of build %s:%s" % \
                    (b.getBuilder().getName(), b.getNumber()))
        name = authz.getUsernameFull(req)
        comments = req.args.get("comments", ["<no reason specified>"])[0]
        comments.decode(getRequestCharset(req))
        # html-quote both the username and comments, just to be safe
        reason = ("The web-page 'Stop Build' button was pressed by "
                  "'%s': %s\n" % (html.escape(name), html.escape(comments)))

        c = interfaces.IControl(self.getBuildmaster(req))
        bldrc = c.getBuilder(self.build_status.getBuilder().getName())
        if bldrc:
            bldc = bldrc.getBuild(self.build_status.getNumber())
            if bldc:
                bldc.stopBuild(reason)

        defer.returnValue(path_to_build(req, self.build_status))

class StopBuildChainActionResource(ActionResource):

    def __init__(self, build_status):
        self.build_status = build_status
        self.action = "stopAllBuilds"

    def stopCurrentBuild(self, master, buildername, number, reason):
        builderc = master.getBuilder(buildername)
        if builderc:
            buildc = builderc.getBuild(number)
            if buildc:
                buildc.stopBuild(reason)
        return buildc

    @defer.inlineCallbacks
    def cancelCurrentBuild(self, master, brids, buildername):
        builderc = master.getBuilder(buildername)
        brcontrols = yield builderc.getPendingBuildRequestControls(brids=brids)
        for build_req in brcontrols:
            if build_req:
                yield build_req.cancel()

        defer.returnValue(len(brcontrols) > 0)

    @defer.inlineCallbacks
    def stopEntireBuildChain(self, master, build, buildername, reason, retry=0):

        if build:
            if retry > 3:
                log.msg("Giving up after 3 times retry, stop build chain: buildername: %s, build # %d" %
                            (buildername, build.build_status.number))
                return

            buildchain = yield build.getBuildChain()
            if len(buildchain) < 1:
                return

            for br in buildchain:
                if br['number'] and br['results'] != RESUME:
                    buildc = self.stopCurrentBuild(master, br['buildername'], br['number'], reason)
                    log.msg("Stopping build chain: buildername: %s, build # %d, brid: %d" %
                            (br['buildername'], br['number'], br['brid']))
                else:
                    # the build was still on the queue
                    canceledrequests = yield self.cancelCurrentBuild(master, [br['brid']], br['buildername'])

                    if not canceledrequests:
                        # the build was removed from queue, we will need to update the build chain list
                        log.msg("Could not cancel build chain: buildername: %s, brid: %d" %
                            (br['buildername'], br['brid']))

                    log.msg("Canceling build chain: buildername: %s, brid: %d" %
                            (br['buildername'], br['brid']))

            # the build chain should be empty by now, will retry any builds that changed state
            buildchain = yield build.getBuildChain()
            if len(buildchain) > 0:
                retry += 1
                log.msg("Retry #%d stop build chain: buildername: %s, build # %d" %
                            (retry, buildername, build.build_status.number))
                yield self.stopEntireBuildChain(master, build, buildername, reason, retry)


    @defer.inlineCallbacks
    def performAction(self, req):
        authz = self.getAuthz(req)
        res = yield authz.actionAllowed(self.action, req, self.build_status)

        if not res:
            defer.returnValue(path_to_authzfail(req))
            return

        b = self.build_status
        log.msg("web stopEntireBuildChain of build %s:%s" % \
                    (b.getBuilder().getName(), b.getNumber()))
        name = authz.getUsernameFull(req)

        reason = ("The web-page 'Stop Entire Build Chain' button was pressed by '%s'\n"
                  % html.escape(name))

        master = interfaces.IControl(self.getBuildmaster(req))
        buildername = self.build_status.getBuilder().getName()
        number = self.build_status.getNumber()

        builderc = master.getBuilder(buildername)
        if builderc:
            build = builderc.getBuild(number)

            if build:
                yield self.stopEntireBuildChain(master, build, buildername, reason)

                build.stopBuild(reason)

        defer.returnValue(path_to_build(req, self.build_status))


# /builders/$builder/builds/$buildnum
class StatusResourceBuild(HtmlResource):
    addSlash = True

    def __init__(self, build_status):
        HtmlResource.__init__(self)
        self.build_status = build_status

    def getPageTitle(self, request):
        return ("%s Build #%d" %
                (self.build_status.getBuilder().getFriendlyName(),
                 self.build_status.getNumber()))

    @defer.inlineCallbacks
    def content(self, req, cxt):
        status = self.getStatus(req)
        cxt = self.__prepare_context(req, cxt)
        slave_obj = None

        is_finished_build = self.build_status.isFinished()
        if is_finished_build:
            cxt['result_css'] = css_classes[self.build_status.getResults()]

        if is_finished_build and self.build_status.getTestResults():
            cxt['tests_link'] = req.childLink("tests")

        try:
            slave_obj = status.getSlave(self.build_status.getSlavename())
        except KeyError:
            pass

        if slave_obj:
            cxt['slave_friendly_name'] = slave_obj.getFriendlyName()
            cxt['slave_url'] = path_to_slave(req, slave_obj)

        if self.build_status.resume:
            cxt['resume'] = self.build_status.resume

        cxt['steps'] = yield get_steps(
            self.build_status.getSteps(),
            getCodebasesArg(req),
            req,
        )

        parameters = self.__get_force_scheduler_parameters(req)
        cxt['properties'] = self.__get_properties(parameters)
        cxt['has_changes'] = any(map(lambda ss: ss.changes, self.build_status.getSourceStamps()))
        cxt['instant_json']['build'] = yield self.__prepare_instant_json(status, req)
        cxt['chained_build'] = yield req.site.buildbot_service.master.db.buildrequests.getBuildChain(
            self.build_status.buildChainID,
        )
        current_build = next(
            ifilter(lambda x: x['id'] in self.build_status.brids, cxt['chained_build']),
            None,
        )

        builder_project = self.build_status.getBuilder().getProject()
        if current_build:
            cxt['top_build_url'], cxt['top_build_name'] = get_url_and_name_build_in_chain(
                current_build['startbrid'],
                cxt['chained_build'],
                builder_project,
                req,
            )
            cxt['parent_build_url'], cxt['parent_build_name'] = get_url_and_name_build_in_chain(
                current_build['triggeredbybrid'],
                cxt['chained_build'],
                builder_project,
                req,
            )

        template = req.site.buildbot_service.templates.get_template("build.html")
        defer.returnValue(template.render(**cxt))

    def stop(self, req, auth_ok=False):
        # check if this is allowed
        if not auth_ok:
            return StopBuildActionResource(self.build_status)

        b = self.build_status
        log.msg("web stopBuild of build %s:%s" % \
                (b.getBuilder().getName(), b.getNumber()))

        name = self.getAuthz(req).getUsernameFull(req)
        comments = req.args.get("comments", ["<no reason specified>"])[0]
        comments.decode(getRequestCharset(req))
        # html-quote both the username and comments, just to be safe
        reason = ("The web-page 'stop build' button was pressed "
                  "'%s': %s\n" % (html.escape(name), html.escape(comments)))

        c = interfaces.IControl(self.getBuildmaster(req))
        bldrc = c.getBuilder(self.build_status.getBuilder().getName())
        if bldrc:
            bldc = bldrc.getBuild(self.build_status.getNumber())
            if bldc:
                bldc.stopBuild(reason)

        # we're at http://localhost:8080/svn-hello/builds/5/stop?[args] and
        # we want to go to: http://localhost:8080/svn-hello
        r = Redirect(path_to_builder(req, self.build_status.getBuilder()))
        d = defer.Deferred()
        reactor.callLater(1, d.callback, r)
        return DeferredResource(d)

    def stopchain(self, req):
        return StopBuildChainActionResource(self.build_status)

    def cancelBuild(self, req):
        return CancelBuildActionResource(self.build_status)

    def getChild(self, path, req):
        if path == "stop":
            return self.stop(req)
        if path == "cancel":
            return self.cancelBuild(req)
        if path == "stopchain":
            return self.stopchain(req)
        if path == "steps":
            return StepsResource(self.build_status)
        if path == "tests":
            return TestsResource(self.build_status)

        return HtmlResource.getChild(self, path, req)

    def __prepare_context(self, request, cxt=None):
        """ This method prepares context for templates

        :param request: http request object
        :param cxt: default context variable
        :type cxt: dictionary
        :return: dictionary with variables for template
        """
        if not cxt:
            context = {}
        else:
            context = cxt.copy()

        builder = self.build_status.getBuilder()

        context['builder_name'] = builder.name
        context['builder_friendly_name'] = builder.getFriendlyName()
        context['selected_project'] = builder.getProject()

        context['build_number'] = self.build_status.getNumber()
        context['custom_build_urls'] = self.build_status.getCustomUrls()
        context['source_stamps'] = self.build_status.getSourceStamps()
        context['got_revisions'] = self.build_status.getAllGotRevisions()
        context['slave_friendly_name'] = self.build_status.getSlavename()
        context['build_reason'] = self.build_status.getReason()
        context['build_is_resuming'] = self.build_status.isResuming()
        context['build_is_finished'] = self.build_status.isFinished()

        context['path_to_builder'] = path_to_builder(request, self.build_status.getBuilder())
        context['path_to_builders'] = path_to_builders(request, builder.getProject())
        context['path_to_codebases'] = path_to_codebases(request, builder.getProject())
        context['build_url'] = path_to_build(request, self.build_status, False)
        context['slave_debug_url'] = self.getBuildmaster(request).config.slave_debug_url
        context['codebases_arg'] = getCodebasesArg(request=request)
        context['parent_build_url'] = None
        context['top_build_url'] = None

        start, end = self.build_status.getTimes()
        context['start'] = time.ctime(start)
        context['end'] = time.ctime(end) if end else None
        if not end:
            end = util.now()
        context['elapsed'] = util.formatInterval(end - start)

        context['authz'] = self.getAuthz(request)
        context['has_changes'] = False
        context['tests_link'] = None
        context['resume'] = None
        context['top_build_name'] = None
        context['parent_build_name'] = None
        context['result_css'] = ""
        context['slave_url'] = ""
        context['steps'] = []
        context['properties'] = []

        return context

    def __get_force_scheduler_parameters(self, request):
        """ This method return dictionary of parameters from scheduler

        :param request: http request object
        :return: dictionary with parameters
        """
        scheduler_name = self.build_status.getProperty("scheduler", None)
        parameters = {}
        scheduler = next(
            ifilter(
                lambda s: s.name == scheduler_name and isinstance(s, ForceScheduler),
                self.getBuildmaster(request).allSchedulers(),
            ),
            None
        )
        if not scheduler:
            return {}

        for p in scheduler.all_fields:
            parameters[p.name] = p

        return parameters

    def __get_properties(self, parameters):
        """ This method prepare properties of build
        TODO refactor

        :param parameters: dictionary with parameter object
        :return: list of properties object
        """
        properties = []
        for name, value, source in self.build_status.getProperties().asList():
            if not isinstance(value, dict):
                cxt_value = unicode(value)
            else:
                cxt_value = value

            if name == 'submittedTime':
                cxt_value = time.ctime(value)

            prop = {
                'name': name,
                'value': cxt_value,
                'short_value': cxt_value[:500],
                'source': source,
            }

            if name in parameters:
                param = parameters[name]
                if isinstance(param, TextParameter):
                    prop['text'] = param.value_to_text(value)
                    prop['cols'] = param.cols
                    prop['rows'] = param.rows
                prop['label'] = param.label
            properties.append(prop)
        return properties

    @defer.inlineCallbacks
    def __prepare_instant_json(self, status, request):
        """ This method prepare instant json variable

        :param status: current build status
        :param request: http request object
        :return: defer with instant json variable
        """
        filters = {
            "number": self.build_status.getNumber()
        }

        build_url = path_to_json_build(
            status,
            request,
            self.build_status.getBuilder().name,
            self.build_status.getNumber(),
        )
        build_dict = yield self.build_status.asDict(request)
        defer.returnValue({
            "url": build_url,
            "data": json.dumps(build_dict, separators=(',', ':')),
            "waitForPush": status.master.config.autobahn_push,
            "pushFilters": {
                "buildStarted": filters,
                "buildFinished": filters,
                "stepStarted": filters,
                "stepFinished": filters,
            }
        })


# /builders/$builder/builds
class BuildsResource(HtmlResource):
    addSlash = True

    def __init__(self, builder_status):
        HtmlResource.__init__(self)
        self.builder_status = builder_status

    def content(self, req, cxt):
        return "subpages shows data for each build"

    def getChild(self, path, req):
        try:
            num = int(path)
        except ValueError:
            num = None
        if num is not None:
            build_status = self.builder_status.getBuild(num)
            if build_status:
                return StatusResourceBuild(build_status)

        return HtmlResource.getChild(self, path, req)

