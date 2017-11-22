/*global define*/
define(function (require) {
    "use strict";

    var $ = require('jquery'),
        realtimePages = require('realtimePages'),
        helpers = require('helpers'),
        dt = require('project/datatables-extend'),
        hb = require('project/handlebars-extend'),
        extendMoment = require('project/moment-extend'),
        timeElements = require('timeElements'),
        rtTable = require('rtGenericTable'),
        popup = require('ui.popup'),
        latestRevDict;

    require('libs/jquery.form');

    var rtBuilderDetail,
        $tbCurrentBuildsTable,
        $tbPendingBuildsTable,
        $tbBuildsTable,
        $tbSlavesTable,
        $tbStartSlavesTable,
        hbBuilderDetail = hb.builderDetail;

    rtBuilderDetail = {
        init: function () {
            $tbCurrentBuildsTable = rtBuilderDetail.currentBuildsTableInit($('#rtCurrentBuildsTable'));
            $tbPendingBuildsTable = rtBuilderDetail.pendingBuildsTableInit($('#rtPendingBuildsTable'));
            $tbBuildsTable = rtTable.table.buildTableInit($('#rtBuildsTable'), false, helpers.urlHasCodebases(), function getLatestRevDict() {
                return latestRevDict;
            });
            $tbSlavesTable = rtBuilderDetail.slavesTableInit($('#rtSlavesTable'));
            $tbStartSlavesTable = rtBuilderDetail.slavesTableInit($('#rtStartSlavesTable'));

            var realtimeFunctions = realtimePages.defaultRealtimeFunctions();
            realtimeFunctions.project = rtBuilderDetail.rtfProcessCurrentBuilds;
            realtimeFunctions.pending_builds = rtBuilderDetail.rtfProcessPendingBuilds;
            realtimeFunctions.builds = rtBuilderDetail.rtfProcessBuilds;
            realtimeFunctions.slaves = rtBuilderDetail.rtfProcessSlaves;
            realtimeFunctions.start_slaves = rtBuilderDetail.rtfProcessStartSlaves;

            realtimePages.initRealtime(realtimeFunctions);

            helpers.selectBuildsAction($tbPendingBuildsTable, false, '/buildqueue/_selected/cancelselected',
                'cancelselected=', rtTable.table.rtfGenericTableProcess);

            //Setup run build
            popup.initRunBuildPopup($(".custom-build"));

            // insert codebase and branch
            helpers.tableHeader($('#brancOverViewCont'));

            helpers.initRecentBuildsFilters();
        },
        rtfProcessCurrentBuilds: function (data) {
            if (data.currentBuilds !== undefined) {
                rtTable.table.rtfGenericTableProcess($tbCurrentBuildsTable, data.currentBuilds);
            }

            if (data.latestRevisions !== undefined) {
                latestRevDict = data.latestRevisions;
            }
        },
        rtfProcessPendingBuilds: function (data) {
            rtTable.table.rtfGenericTableProcess($tbPendingBuildsTable, data);
        },
        rtfProcessSlaves: function (data) {
            data = helpers.objectPropertiesToArray(data);
            rtTable.table.rtfGenericTableProcess($tbSlavesTable, data);
        },
        rtfProcessStartSlaves: function (data) {
            data = helpers.objectPropertiesToArray(data);
            rtTable.table.rtfGenericTableProcess($tbStartSlavesTable, data);
        },
        rtfProcessBuilds: function (data) {
            rtTable.table.rtfGenericTableProcess($tbBuildsTable, data);
        },
        currentBuildsTableInit: function ($tableElem) {
            var options = {};

            options.oLanguage = {
                "sEmptyTable": "No current builds"
            };

            options.aoColumns = [
                {"mData": null, "sTitle": "#", "sWidth": "10%"},
                {"mData": null, "sTitle": "Current build", "sWidth": "30%"},
                {"mData": null, "sTitle": "Revision", "sWidth": "35%"},
                {"mData": null, "sTitle": "Author", "sWidth": "25%", "sClass": "txt-align-right"}
            ];

            options.aoColumnDefs = [
                rtTable.cell.buildID(0),
                rtTable.cell.buildProgress(1, true),
                rtTable.cell.revision(2, "sourceStamps", helpers.urlHasCodebases()),
                {
                    "aTargets": [3],
                    "sClass": "txt-align-left",
                    "mRender": function (data, type, full) {
                        var author = 'N/A';
                        if (full.properties !== undefined) {
                            $.each(full.properties, function (i, prop) {
                                if (prop[0] === "owner") {
                                    author = prop[1];
                                }
                            });
                        }
                        return author;
                    }
                }
            ];

            return dt.initTable($tableElem, options);
        },
        pendingBuildsTableInit: function ($tableElem) {
            var options = {};

            options.oLanguage = {
                "sEmptyTable": "No pending builds"
            };

            options.aoColumns = [
                {"mData": null, "sWidth": "4%", "sTitle": "", bSortable: false},
                {"mData": null, "sWidth": "21%", "sTitle": "Priority", bSortable: false},
                {"mData": null, "sWidth": "17%", "sTitle": "When", bSortable: false},
                {"mData": null, "sWidth": "21%", "sTitle": "Waiting", bSortable: false},
                {"mData": null, "sWidth": "21%", "sTitle": "Branch", bSortable: false},
                {"mData": "brid", "sWidth": "17%"}
            ];

            options.aoColumnDefs = [
                {
                    "aTargets": [0],
                    "sClass": "txt-align-center",
                    "mRender": function (data, type, full) {
                        // If the build result is not resume then we are in the normal queue and not the
                        // resume queue
                        return helpers.getPendingIcons(hb, data);
                    }
                },
                {
                    "aTargets": [1],
                    "sClass": "txt-align-center",
                    "mRender": function (data, type, full) {
                        return helpers.getPriorityData(data, full);
                    }
                },
                {
                    "aTargets": [2],
                    "sClass": "txt-align-left",
                    "mRender": function (data, type, full) {
                        return extendMoment.getDateFormatted(full.submittedAt);
                    }
                },
                {
                    "aTargets": [3],
                    "sClass": "txt-align-left",
                    "mRender": function () {
                        return hbBuilderDetail({pendingBuildWait: true});
                    },
                    "fnCreatedCell": function (nTd, sData, oData) {
                        timeElements.addElapsedElem($(nTd).find('.waiting-time-js'), oData.submittedAt);
                    }
                },
                rtTable.cell.revision(4, "sources", helpers.urlHasCodebases()),
                {
                    "aTargets": [5],
                    "sClass": "txt-align-right",
                    "mRender": function (data, type, full) {
                        return hbBuilderDetail({removeBuildSelector: true, data: full});
                    }
                },
                {
                    "aTargets": [ 6 ],
                    "sClass": "select-input",
                    "mRender": function (data, type, full) {
                        return hbBuilderDetail({input: 'true', brid: full.brid});
                    }
                }
            ];

            return dt.initTable($tableElem, options);
        },
        slavesTableInit: function ($tableElem) {
            var options = {};

            options.oLanguage = {
                "sEmptyTable": "No slaves attached"
            };

            options.aoColumns = [
                {"mData": null, "sWidth": "50%", "sTitle": "Slave"},
                {"mData": null, "sWidth": "50%", "sTitle": "Status"}
            ];

            options.aoColumnDefs = [
                rtTable.cell.slaveName(0, "friendly_name", "url"),
                rtTable.cell.slaveStatus(1)
            ];

            return dt.initTable($tableElem, options);
        }
    };

    return rtBuilderDetail;
});
