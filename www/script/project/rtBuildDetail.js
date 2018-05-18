/*global define, Handlebars */
define(function (require) {
    "use strict";

    var $ = require('jquery'),
        realtimePages = require('realtimePages'),
        helpers = require('helpers'),
        timeElements = require('timeElements'),
        popups = require('ui.popup'),
        qs = require('libs/query-string'),
        hb = require('project/handlebars-extend'),
        hbBuild = hb.build,
        hbStopBuild = hb.stop_build;

    var rtBuildDetail,
        isLoaded = false,
        noMoreReloads = false,
        debug = qs.parse(location.search).debug === "true",
        messages = {
            ONE_BUILD: "This will cancel this build.\n\nAre you sure you want to cancel this build?",
            CHAINED_BUILD: "This will cancel all builds in this chain, which may take a little while.\n" +
                           "These build will also be affected: \n\n" +
                           "{0}\n\nAre you sure you want to cancel those builds?"
        };

    rtBuildDetail = {
        init: function () {
            var realtimeFunctions = realtimePages.defaultRealtimeFunctions();
            realtimeFunctions.build = rtBuildDetail.processBuildDetailPage;
            realtimePages.initRealtime(realtimeFunctions);
            timeElements.setHeartbeat(1000);

            // insert codebase and branch on the builders page
            helpers.tableHeader($('.top'));

            //Allow for popups
            $(".popup-btn-js-2").bind("click.katana", function (e) {
                e.preventDefault();
                var $elem = $(e.target);
                var html = $elem.next(".more-info-box-js").html(),
                    $body = $("body"),
                    $popup = $("<div/>").popup({
                        title: "",
                        html: html,
                        destroyAfter: true
                    });

                $body.append($popup);
            });


            // Setup dialog for stop entire chain
            $("form[data-stop-chain]").ajaxForm({
                beforeSubmit: function beforeSubmit(data, $form) {
                    var chainBuild = $form.data("chain").toString();
                    var deleteMsgKey = $form.data('msg-label') || 'ONE_BUILD';
                    return confirm(messages[deleteMsgKey].format(chainBuild));
                }
            });

            $('button[data-stop-build-url]').click(function() {
                var prop = {
                    one_build: $(this).data('single-build') !== undefined,
                    chained_build: $(this).data('chain-builds') !== undefined,
                    builds_in_chain: $(this).data('chain-builds'),
                    url: $(this).data('stop-build-url')
                };
                var $popup = $("<div/>").popup({
                    destroyAfter: true,
                    closeButton: false,
                    html: hbStopBuild(prop),
                    onCreate: function($elem) {
                        $elem.on('click', '.close-button', $elem.hidePopup);
                        $elem.on('click', '.confirm-button', function() {
                            $('.confirm-button, .close-button').hide();
                            $('#loading-modal').show();
                            $.post($(this).data('url'), {}, function() {
                                $elem.hidePopup();
                                location.reload();
                            });
                        });
                    }
                });
                $("body").append($popup);
            });

            // Setup build buttons
            popups.initRunBuildPopup($(".custom-build"), $(".instant-build"), true);
            popups.initRebuildPopup($(".custom-rebuild"), true);
        },
        processBuildDetailPage: function (data) {
            //We get slighlty different data objects from autobahn
            var keys = Object.keys(data);
            if (keys.length === 1) {
                data = data[keys[0]];
            }

            var buildStartTime = data.times[0],
                buildEndTime = data.times[1],
                buildFinished = (buildEndTime !== null),
                eta = data.eta;

            rtBuildDetail.refreshIfRequired(buildFinished);

            //Process Page
            rtBuildDetail.processBuildResult(data, buildStartTime, eta, buildFinished);
            rtBuildDetail.processSteps(data);
            rtBuildDetail.processArtifacts(data);

            //If build is running
            if (buildEndTime === null) {
                //Elapsed Time & Progress Bar
                timeElements.addElapsedElem($('#elapsedTimeJs'), buildStartTime);
            }

            timeElements.updateTimeObjects();
        },
        processBuildResult: function (data, startTime, eta, buildFinished) {
            var $buildResult = $('#buildResult');
            timeElements.clearTimeObjects($buildResult);
            var progressBar = "";
            if (eta !== 0) {
                progressBar = hb.partials.build["build:progressBar"]({progressBar: true, etaStart: startTime, etaCurrent: eta});
            }

            var props = {
                buildResults: true,
                b: data,
                buildIsFinished: buildFinished,
                progressBar: progressBar
            };

            var html = hbBuild(props);
            $buildResult.html(html);

            var $progressBar = $buildResult.find(".percent-outer-js");
            $progressBar.addClass("build-detail-progress");
            helpers.delegateToProgressBar($progressBar);
        },
        /* Setup `hasDependency` and `hasArtifacts` flags based on `url` and `is_not_skipped`
           values from backend
           @return stepData with above flags.
        */
        setup_dependencies_and_artifacts_flags: function(stepData){
            $.each(stepData.urls, function (j, url) {
                stepData.hasDependency = false;
                stepData.hasArtifacts = true;
                if (url.url !== undefined) {
                    stepData.hasArtifacts = false;
                    if(stepData.is_skipped === false){
                        stepData.hasDependency = true;
                    }
                }
                return true;
            });
            return stepData;
        },
        processSteps: function (data) {
            var html = "";
            var $stepList = $('#stepList');
            var count = 1;
            /*jslint unparam: true*/
            $.each(data.steps, function (i, stepData) {
                if (stepData.hidden && !debug) {
                    return true;
                }

                var started = stepData.isStarted;
                var finished = stepData.isFinished;

                var status = stepData.results[0];
                if (!started) {
                    status = helpers.cssClassesEnum.NOT_STARTED;
                } else if (started && !finished) {
                    status = helpers.cssClassesEnum.RUNNING;
                }

                stepData = rtBuildDetail.setup_dependencies_and_artifacts_flags(stepData);

                var cssClass = helpers.getCssClassFromStatus(status);
                var startTime = stepData.times[0];
                var endTime = stepData.times[1];
                var runTime = helpers.getTime(startTime, endTime);
                var props = {
                    step: true,
                    index: count,
                    stepStarted: stepData.isStarted,
                    run_time: runTime,
                    css_class: cssClass,
                    s: stepData,
                    url: stepData.url
                };
                html += hbBuild(props);
                count += 1;

                return true;
            });
            /*jslint unparam: false*/

            $stepList.html(html);
        },
        processArtifacts: function (data) { // for the builddetailpage. Puts the artifacts and testresuts on top
            var $artifactsJSElem = $("#artifacts-js").empty(),
                artifactsDict = {},
                testLogsDict = {},
                html;

            /*jslint unparam: true*/
            $.each(data.steps, function (i, obj) {
                if (obj.urls !== undefined) {
                    $.each(obj.urls, function (name, url) {
                        if (typeof url === "string") {
                            artifactsDict[name] = url;
                        }
                    });
                }
            });
            var reportSource = $.grep(data.logs, function(obj){ return obj[1].indexOf(".json") > -1; });
            if(!reportSource.length) {
                reportSource = $.grep(data.logs, function (obj) {
                    return obj[1].indexOf(".xml") > -1;
                });
            }
            var htmlReport = $.grep(data.logs, function(obj){ return obj[1].indexOf(".html") > -1; });

            $.each(reportSource.concat(htmlReport), function(i, obj){ testLogsDict[obj[0]] = obj[1] ;} );

            /*jslint unparam: false*/

            if (artifactsDict === undefined || Object.keys(artifactsDict).length === 0) {
                $artifactsJSElem.html("No artifacts");
            } else {
                html = '<a class="artifact-popup artifacts-js more-info" href="#">Artifacts ({0})&nbsp;</a>'.format(Object.keys(artifactsDict).length);
                $artifactsJSElem.html(html);

                popups.initArtifacts(artifactsDict, $artifactsJSElem.find(".artifact-popup"));
            }

            if (Object.keys(testLogsDict).length > 0) {
                html = '<li>Test Results</li>';

                $.each(testLogsDict, function (url, name) {
                    html += '<li class="s-logs-js"><a href="{0}">{1}</a></li>'.format(name, url);
                });

                html = $("<ul/>").addClass("tests-summary-list list-unstyled").html(html);

                $artifactsJSElem.append(html);
            }

            return html;
        },
        refreshIfRequired: function (buildFinished) {
            //Deal with page reload
            if (!noMoreReloads && isLoaded && buildFinished) {
                window.location = window.location + '#finished';
                window.location.reload();
            }
            if (noMoreReloads === false) {
                noMoreReloads = buildFinished;
            }

            isLoaded = true;
        }
    };

    return rtBuildDetail;
});
