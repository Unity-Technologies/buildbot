# This class is used for updating dependency trigger statuses without having to wait for the dependencies to finish
# Each tuple/message object is in the format:
# "ID of build chain", "name of build (not friendlyName)", object reference of status to be changed

from twisted.python import log

# A simple array is enough to keep track of all the status object tuples. There should be very few ones concurrently.
current_messageobjects = []


def add_new_status(build_chain_id, build_name, status_obj):
    """
    Adds a "trigger build" step's status object to an array, for writing to by a dependency build.
    This is called with every dependency trigger, and once per dependency.
    @param build_chain_id: int - the ID of the build chain involved in the trigger
    @param build_name: string - the name of the build being triggered
    @param status_obj: buildstatus object - from the build step calling the trigger
    @return: None
    """
    build_tuple = (build_chain_id, build_name, status_obj)
    current_messageobjects.append(build_tuple)

    # This check is temporary, to make sure there's no errors preventing tuples from being cleared out after use
    if len(current_messageobjects) > 50:
        messagecount = len(current_messageobjects)
        log.msg("WARNING: buildstatusupdater.current_messageobjects has an unexpectedly large number of objects (%s).", messagecount)
        # And let's make sure to not break Katana if it actually goes overboard
        if messagecount > 200:
            log.msg("WARNING: buildstatusupdater.current_messageobjects has far too many objects. Removing oldest...")
            current_messageobjects.pop(0)


def set_statuses(build_chain_id, build_name, url_obj):
    """
    Given the build's name and ID, checks if any "trigger build" build steps are expecting it, and if so, adds a URL to
    their status objects. Then removes that status object from the list.
    This is called at the start of every build.
    @param build_chain_id: int - the ID of the build chain involved in the build
    @param build_name: string - the name of the current build
    @param url_obj:`object containing the URL details of the current build
    @return: None
    """
    for build_tuple in current_messageobjects:
        if build_tuple[0] == build_chain_id:
            if build_tuple[1] == build_name:
                status_obj = build_tuple[2]
                status_obj.addURL(url_obj['text'], url_obj['path'], 0)
                # we're done with this status object, so remove the tuple from the list
                current_messageobjects.remove(build_tuple)
                break


def remove_all_matching_statusobj(status_obj):
    """
    Called at the end of a "trigger dependency" build step, to remove any status objects that may still be hanging around
    (eg: from builds that failed to start).
    @param status_obj: the status object of the build step.
    @return: None
    """
    for build_tuple in current_messageobjects:
        if build_tuple[2] == status_obj:
            current_messageobjects.remove(build_tuple)
            # Can't edit a list while still iterating through it, so use recursion instead.
            return remove_all_matching_statusobj(status_obj)
