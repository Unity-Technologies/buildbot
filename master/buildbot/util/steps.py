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
import urllib

from twisted.internet import defer

from buildbot import util
from buildbot.status.web.base import css_classes
from buildbot.status.web.base import path_to_step


@defer.inlineCallbacks
def get_steps(steps_list, codebases_arg, request):
    """ This function return steps list with full description

    :param steps_list: list of steps in build
    :param codebases_arg: additional parameters for url
    :param request: http request object
    :return:
    """
    steps = []
    for step in steps_list:
        step_obj = {
            'name': step.getName(),
            'css_class': 'not-started',
            'time_to_run': '',
            'link': path_to_step(request, step),
            'text': ' '.join(step.getText()),
            'urls': [],
            'logs': [],
        }
        if step.isFinished and step.isHidden():
            continue

        if step.isFinished():
            start, end = step.getTimes()
            step_obj['css_class'] = css_classes[step.getResults()[0]]
            step_obj['time_to_run'] = util.formatInterval(end - start)
        elif step.isStarted():
            is_waiting = step.isWaitingForLocks()
            step_obj['css_class'] = 'waiting' if is_waiting else 'running'
            step_obj['time_to_run'] = 'waiting for locks' if is_waiting else 'running'

        # TODO Remove side effect
        yield step.prepare_trigger_links()

        step_obj['urls'] = __prepare_url_object(step, codebases_arg)
        step_obj['logs'] = __get_logs_for_step(step, codebases_arg, request)

        steps.append(step_obj)
    yield steps


def __get_logs_for_step(step, codebases_arg, request):
    logs = []
    for log in step.getLogs():
        log_name = log.getName()
        link = "steps/{}/logs/{}{}".format(
            urllib.quote(step.getName(), safe=''),
            urllib.quote(log_name, safe=''),
            codebases_arg,
        )
        logs.append({
            'link': request.childLink(link),
            'name': log_name,
        })
    return logs


def __prepare_url_object(step, codebases_arg):
    urls = []
    for k, v in step.getURLs().items():
        if isinstance(v, dict):
            if 'results' in v.keys() and v['results'] in css_classes:
                url_dict = dict(logname=k, url=v['url'] + codebases_arg,
                                results=css_classes[v['results']])
            else:
                url_dict = dict(logname=k, url=v['url'] + codebases_arg)
        else:
            url_dict = dict(logname=k, url=v + codebases_arg)
        urls.append(url_dict)
    return urls
