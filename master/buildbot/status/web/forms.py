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
from operator import attrgetter
import urllib
from urlparse import urlunparse, urlparse
from twisted.internet import defer
from twisted.web._responses import INTERNAL_SERVER_ERROR
from twisted.web.resource import ErrorPage

from buildbot.status.web.builder import buildForceContext, buildForceContextForSingleFieldWithValue
from buildbot.status.web.base import HtmlResource, getRequestCharset


class FormsKatanaResource(HtmlResource):
    pageTitle = "Forms"

    def content(self, request, cxt):
        cxt.update(content = "<h1>Page not found.</h1>")
        template = request.site.buildbot_service.templates.get_template("empty.html")
        return template.render(**cxt)

    def getChild(self, path, req):
        if path == "forceBuild":
            return ForceBuildDialogPage()
        elif path == "rebuild":
            return RebuildDialogPage()

class BuildDialogPage(HtmlResource):
    def decodeFromURL(self, value, encoding):
        return urllib.unquote(value).decode(encoding)

    def _decodeRequestArgs(self, request, encoding):
        requestArgs = request.args.copy()
        for name, argl in requestArgs.iteritems():
            if '_branch' in name:
                requestArgs[name] = [self.decodeFromURL(arg, encoding) for arg in argl]
        return requestArgs

    def _getSlaves(self, builder_status):
        slaves = [s for s in builder_status.getSlaves() if s.isConnected()]
        return sorted(slaves, key=attrgetter('friendly_name'))

    def _getBranches(self, requestArgs, request):
        encoding = getRequestCharset(request)
        return [b.decode(encoding) for b in requestArgs.get("branch", []) if b]

    @defer.inlineCallbacks
    def _getIsAdmin(self, request):
        authz = self.getAuthz(request)
        isAdmin = yield authz.getUserAttr(request, 'is_admin', 0)
        defer.returnValue(isAdmin)

    def _getReturnPage(self, requestArgs, builderUrl):
        return_page = requestArgs.get('return_page', '')
        if not isinstance(return_page, basestring):
            return_page = return_page[0]

        if builderUrl.query:
            return "&returnpage={0}".format(return_page)
        else:
            return "?returnpage={0}".format(return_page)

    def _getForceUrl(self, return_page, builderUrl):
        path = builderUrl.path + '/force'
        query = builderUrl.query + return_page
        forceUrl = builderUrl._replace(path=path, query=query)
        return urlunparse(forceUrl)


class ForceBuildDialogPage(BuildDialogPage):
    pageTitle = "Force Build"

    @defer.inlineCallbacks
    def content(self, request, cxt):
        status = self.getStatus(request)
        encoding = getRequestCharset(request)
        requestArgs = self._decodeRequestArgs(request, encoding)

        #Get builder info
        builder_status = None
        if "builder_name" in requestArgs and len(requestArgs["builder_name"]) == 1:
            builder_status = status.getBuilder(self.decodeFromURL(requestArgs["builder_name"][0], encoding))
            buildMaster = self.getBuildmaster(request)

            cxt['slaves'] = self._getSlaves(builder_status)
            cxt['branches'] = self._getBranches(requestArgs, request)

            buildForceContext(cxt, request, buildMaster, builder_status.getName())

            builderUrl = urlparse(requestArgs['builder_url'][0])
            cxt['return_page'] = self._getReturnPage(requestArgs, builderUrl)
            cxt['force_url'] = self._getForceUrl(cxt['return_page'], builderUrl)

            cxt['is_admin'] = yield self._getIsAdmin(request)
            cxt['rt_update'] = requestArgs
            request.args = requestArgs

            template = request.site.buildbot_service.templates.get_template("force_build_dialog.html")
            defer.returnValue(template.render(**cxt))

        else:
            page = ErrorPage(INTERNAL_SERVER_ERROR, "Missing parameters", "Not all parameters were given")
            defer.returnValue(page.render(request))

class RebuildDialogPage(BuildDialogPage):
    pageTitle = "Rebuild"

    @defer.inlineCallbacks
    def content(self, request, cxt):
        status = self.getStatus(request)
        encoding = getRequestCharset(request)
        requestArgs = self._decodeRequestArgs(request, encoding)

        # Get build info
        buildNumber = self._getSingleArgument(requestArgs, encoding, "build_number")
        builderName = self._getSingleArgument(requestArgs, encoding, "builder_name")

        if buildNumber is not None and builderName is not None:
            builder_status = status.getBuilder(builderName)
            build = builder_status.getBuild(int(buildNumber))
            buildMaster = self.getBuildmaster(request)

            cxt['slaves'] = self._getSlaves(builder_status)
            cxt['branches'] = self._getBranches(requestArgs, request)

            buildForceContext(cxt, request, buildMaster, builder_status.getName())
            self._overrideForceContext(request, cxt, build, buildMaster, builderName)

            builderUrl = urlparse(requestArgs['builder_url'][0])
            cxt['return_page'] = self._getReturnPage(requestArgs, builderUrl)
            cxt['force_url'] = self._getForceUrl(cxt['return_page'], builderUrl)

            cxt['is_admin'] = yield self._getIsAdmin(request)
            cxt['rt_update'] = requestArgs
            request.args = requestArgs

            template = request.site.buildbot_service.templates.get_template("force_build_dialog.html")
            defer.returnValue(template.render(**cxt))

        else:
            page = ErrorPage(INTERNAL_SERVER_ERROR, "Missing parameters", "Not all parameters were given")
            defer.returnValue(page.render(request))

    def _getSingleArgument(self, requestArgs, encoding, name, default=None):
        if name in requestArgs and len(requestArgs[name]) == 1:
            return self.decodeFromURL(requestArgs[name][0], encoding)
        return default

    def _overrideForceContextForField(self, defaultProps, scheduler, field, build, buildMaster, builderName):

        if build.properties.hasProperty(field.name):
            propertyValue = build.properties.getProperty(field.name, None)
            buildForceContextForSingleFieldWithValue(defaultProps, scheduler, field, buildMaster, builderName, propertyValue)

        if "nested" in field.type:
            for subfield in field.fields:
                self._overrideForceContextForField(defaultProps, scheduler, subfield, build, buildMaster, builderName)

    def _overrideCodebaseSubfield(self, defaultProps, scheduler, field, buildMaster, builderName, name, value):
        for subfield in field.fields:
            if subfield.name == name:
                buildForceContextForSingleFieldWithValue(defaultProps, scheduler, subfield, buildMaster, builderName, value)
                break

    def _overrideForceContextCodebase(self, defaultProps, scheduler, field, build, buildMaster, builderName):
        if "nested" not in field.type:
            return

        for source in build.sources:
            if source.codebase == field.codebase:
                self._overrideCodebaseSubfield(defaultProps, scheduler, field, buildMaster, builderName, "project", source.project)
                self._overrideCodebaseSubfield(defaultProps, scheduler, field, buildMaster, builderName, "branch", source.branch)
                self._overrideCodebaseSubfield(defaultProps, scheduler, field, buildMaster, builderName, "revision", source.revision)
                self._overrideCodebaseSubfield(defaultProps, scheduler, field, buildMaster, builderName, "repository", source.repository)
                break

    def _overrideForceContext(self, request, cxt, build, buildMaster, builderName):

        defaultProps = cxt['default_props']

        # Override sourcestamp properties: "<scheduler>.<codebasename>_<propertyname>"
        forceSchedulers = cxt['force_schedulers']
        for schedulerName, scheduler in forceSchedulers.iteritems():
            for field in scheduler.all_fields:
                if field.name == 'force_rebuild':
                    buildForceContextForSingleFieldWithValue(defaultProps, scheduler, field, buildMaster, builderName, value=True)
                elif 'codebase' in field.type:
                    self._overrideForceContextCodebase(defaultProps, scheduler, field, build, builderName, builderName)
                else:
                    self._overrideForceContextForField(defaultProps, scheduler, field, build, buildMaster, builderName)
