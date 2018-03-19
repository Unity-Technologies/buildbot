import datetime
import json


def __get_json(failure_):
    failure_dict = {
        'type': str(type(failure_.type())),
        'value': str(failure_.value),
        'msg': str(failure_),
        'datetime': str(datetime.datetime.now()),
    }
    if failure_.frames:
        failure_dict.update({
            'method': failure_.frames[0][0],
            'file': failure_.frames[0][1],
            'line': failure_.frames[0][2],
        })
    return json.dumps(failure_dict)


def err_json(_stuff=None, _why=None, **kw):
    """
    Based on twisted.python.log.err
    """
    from twisted.python import failure
    from twisted.python import log

    if _stuff is None:
        _stuff = failure.Failure()
    if isinstance(_stuff, failure.Failure):
        log.msg(__get_json(_stuff), why=_why, isError=1, **kw)
    elif isinstance(_stuff, Exception):
        log.msg(__get_json(failure.Failure(_stuff)), why=_why, isError=1, **kw)
    else:
        log.msg(repr(_stuff), why=_why, isError=1, **kw)
