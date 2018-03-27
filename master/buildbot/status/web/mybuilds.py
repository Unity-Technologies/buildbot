from twisted.internet import defer

from buildbot.util.build import prepare_mybuilds
from buildbot.status.web.base import HtmlResource


class MybuildsResource(HtmlResource):
    pageTitle = "MyBuilds"

    @defer.inlineCallbacks
    def content(self, req, cxt):
        master = self.getBuildmaster(req)
        user_id = cxt['authz'].getUserInfo(cxt['authz'].getUsername(req))['uid']

        cxt['builds'] = yield prepare_mybuilds(master, user_id)
        cxt['days_count'] = master.config.myBuildDaysCount
        template = req.site.buildbot_service.templates.get_template("mybuilds.html")
        template.autoescape = True
        defer.returnValue(template.render(**cxt))
