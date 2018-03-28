from buildbot.status.results import RESULT_TO_CSS, Results


def add_css_classes_to_results(builds):
    """
    Change build['results'] <int> to human name and suitable CSS class
    Add new information as new keys and values in build <dict>
    Use new copy of dicts instead in-place update.

    @param builds: list of builds (dicts)
    @return: new list of builds with CSS data (name, class)
    """
    builds_with_css = []
    for build_ in builds:
        build = build_.copy()
        build['result_css_class'] = RESULT_TO_CSS.get(build['results'], "")
        build['result_name'] = Results[build['results']] if build['results'] >= 0 else "running"
        builds_with_css.append(build)
    return builds_with_css
