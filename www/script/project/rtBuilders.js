/*global define, Handlebars*/
define(function (require) {
    "use strict";

   var $ = require('jquery'),
        realtimePages = require('realtimePages'),
        helpers = require('helpers'),
        dt = require('project/datatables-extend'),
        rtTable = require('rtGenericTable'),
        popup = require('ui.popup'),
        hb = require('project/handlebars-extend'),
        MiniSet = require('project/sets'),
        URI = require('libs/uri/URI'),
        $tbSorter,
        initializedCodebaseOverview = false,
        latestRevDict = {},
        tags = new MiniSet(),
        branch_tags = new MiniSet(),// All of the tags that only contain a branch i.e 4.6, Trunk
        tagAsBranchRegex = /^(20[0-9][0-9].[0-9]|[0-9].[0-9]|trunk)$/i, // Regex for finding tags that are named the same as branches
        savedTags = [],
        $tagsSelect,
        NO_TAG = "No Tag",
        UNSTABLE_TAG = "Unstable",
        WIP_TAG = "WIP",
        tagSeparator = " && ",
        extra_tags = [NO_TAG],
        MAIN_REPO = "unity_branch",
        hideUnstable = false,
        $searchField;

    require('libs/jquery.form');
    require('libs/absolute');

    var rtBuilders = {
        init: function () {
            $.fn.dataTableExt.afnFiltering.push(rtBuilders.filterByTags(0));
            $tbSorter = rtBuilders.dataTableInit($('.builders-table'));
            var realtimeFunctions = realtimePages.defaultRealtimeFunctions();
            realtimeFunctions.builders = rtBuilders.realtimeFunctionsProcessBuilders;
            realtimePages.initRealtime(realtimeFunctions);

            $searchField = $(".dataTables_filter>label input");

            // Listen for history changes
            window.addEventListener('popstate', function (event) {
                rtBuilders.loadStateFromURL();
            });

            helpers.tooltip($("[data-title]"));
        },
        realtimeFunctionsProcessBuilders: function (data) {
            if (initializedCodebaseOverview === false) {
                initializedCodebaseOverview = true;

                // insert codebase and branch on the builders page
                rtBuilders.findAllTags(data.builders);
                helpers.tableHeader($('.dataTables_wrapper .top'), data.comparisonURL, tags.keys().sort());

                var $unstableButton = $("#btn-unstable");
                $unstableButton.click(function () {
                    hideUnstable = !hideUnstable;
                    rtBuilders.updateUnstableButton();
                    $tbSorter.fnDraw();
                });
                rtBuilders.updateUnstableButton();


                rtBuilders.updateTagsForSelect2(true);
            }
            latestRevDict = data.latestRevisions;
            rtTable.table.rtfGenericTableProcess($tbSorter, data.builders);

        },
        updateTagsForSelect2: function updateTagsForSelect2(allowInit) {
            if ($tagsSelect === undefined && allowInit) {
                $tagsSelect = $("#tags-select");

                $tagsSelect.on("change", function change() {
                    $tbSorter.fnDraw();
                });
            }

            if ($tagsSelect !== undefined) {
                var str = "";
                $.each(savedTags, function (i, tag) {
                    str += tag + ",";
                });
                $tagsSelect.val(str);

                $tagsSelect.select2({
                    multiple: true,
                    data: rtBuilders.parseTags()
                });
                $tbSorter.fnDraw();
            }
        },
        parseTags: function parseTags() {
            var results = [];
            $.each(tags.keys(), function (i, tag) {
                results.push({id: tag, text: tag})
            });
            return {results: results};
        },
        saveState: function saveState(oSettings, oData) {
            if (history.pushState) {
                var search = oData.search !== undefined ? oData.search.search : "";
                rtBuilders.saveStateToURL(search);

                // Remove search as it's found in the URI
                oData.search = undefined;
            }

            return true;
        },
        loadState: function loadState(oSettings, oData) {
            rtBuilders.loadStateFromURL(oData);
            return true;
        },
        findAllTags: function findAllTags(data) {
            var branch_type = rtBuilders.getBranchType();

            tags.clear();
            $.each(data, function eachBuilder(i, builder) {
                var builderTags = rtBuilders.formatTags(builder.tags, branch_type);
                tags.add(builderTags);

                $.each(builder.tags, function eachBuilderTag(i, tag) {
                    // If we found a branch tag then add it
                    if (tagAsBranchRegex.exec(tag)) {
                        branch_tags.add(tag.toLowerCase());
                    }
                });

                if (builderTags.length > 1){
                    tags.add(builderTags.join(tagSeparator));
                }
            });

            tags.add(extra_tags)
        },
        getSelectedTags: function getSelectedTags() {
            var selectedTags = [];
            if ($tagsSelect !== undefined && $tagsSelect.val() !== undefined) {
                $.each($tagsSelect.val().split(","), function (i, tag) {
                    if (tag.length) {
                        selectedTags.push(tag.trim());
                    }
                });
            }

            return selectedTags;
        },
        filterByTags: function filterByTags(col) {
            return function (settings, filterData, row, data) {
                var selectedTags = rtBuilders.getSelectedTags(),
                    builderTags = data.tags,
                    branch_type = rtBuilders.getBranchType(),
                    hasBranch = function (b) {
                        if (branch_type === undefined) {
                            return true;
                        }
                        return b.toLowerCase() === branch_type.toLowerCase();
                    };

                if (hideUnstable === true && ($.inArray(UNSTABLE_TAG, builderTags) > -1 || $.inArray(WIP_TAG, builderTags) > -1)) {
                    return false;
                }

                var filteredTags = rtBuilders.filterTags(builderTags, branch_type);

                if (selectedTags.length == 0 && (builderTags.length > 0 && filteredTags.length === 0 || builderTags.length !== filteredTags.length)) {
                    return builderTags.some(hasBranch);
                }

                if (selectedTags.length === 0) {
                    return true;
                }

                if (builderTags.length === 0) {
                    return $.inArray(NO_TAG, selectedTags) > -1;
                }

                var result = false;
                if ($.inArray(NO_TAG, selectedTags) > -1) {
                    selectedTags.push(branch_type);
                }

                if(filteredTags.length > 1) {
                    filteredTags.push(filteredTags.join(tagSeparator));
                }

                $.each(selectedTags, function eachSelectedTag(i, tag) {
                    if ((tag === NO_TAG && filteredTags.length === 0 && builderTags.some(hasBranch)) || ($.inArray(tag, filteredTags) > -1)) {
                        result = true;
                        return false;
                    }
                });
                return result;
            };
        },
        getBranchType: function getBranchType() {
            var branches = helpers.codebasesFromURL({}),
                regex = [
                    /^(trunk)/,                 // Trunk
                    /^(20[0-9][0-9].[0-9])\//,  // 2017.1/
                    /^([0-9].[0-9])\//,         // 5.0/
                    /^release\/([0-9].[0-9])/   // release/4.6
                ],
                branch_type = undefined;

            $.each(regex, function eachRegex(i, r) {
                $.each(branches, function eachBranch(repo, b) {
                    b = decodeURIComponent(b);
                    var matches = r.exec(b);
                    if (matches !== null && matches.length > 0) {
                        branch_type = matches[1];
                        return false;
                    }
                });
            });

            // If the branch is not found as one of the branch tags i.e 4.5, then default to trunk
            // or if the main repo is being used on this page then also default to trunk
            if ((branch_type !== undefined && $.inArray(branch_type, branch_tags.keys()) === -1) ||
                (branch_type === undefined && $.inArray(MAIN_REPO, Object.keys(branches)) > -1 &&
                branches[MAIN_REPO] !== undefined && branches[MAIN_REPO].length)) {
                return "trunk"; // Default to trunk
            }

            return branch_type;
        },
        filterTags: function filterTags(tags) {
            var branch_type = rtBuilders.getBranchType();

            var filtered_tags = tags.filter(function (tag) {
                return rtBuilders.tagVisibleForBranch(tag, branch_type)
            });


            return  rtBuilders.formatTags(filtered_tags, branch_type).sort();
        },
        formatTags: function formatTags(tags, branch_type) {
            var formatTag = function (tag) {
                if (tag.indexOf("-") > -1) {
                    return tag.replace(new RegExp(branch_type + "-", "gi"), "");
                }

                return tag;
            };

            if (Array.isArray(tags)) {
                var output = [];
                $.each(tags, function eachTag(i, tag) {
                    var formatted_tag = formatTag(tag);
                    if (rtBuilders.tagVisibleForBranch(tag, branch_type) &&
                        $.inArray(formatted_tag, output) === -1) {
                        output.push(formatTag(tag));
                    }
                });
                return output;
            }

            return formatTag(tags);
        },
        tagVisibleForBranch: function tagVisibleForBranch(tag, branch_type) {
            if (branch_type === undefined) {
                return true;
            }
            if (tag.indexOf("-") > -1) {
                return tag.toLowerCase().indexOf(branch_type.toLowerCase()) > -1;
            }
            return !tagAsBranchRegex.exec(tag);
        },
        setHideUnstable: function setHideUnstable(hidden) {
            hideUnstable = hidden;
        },
        isUnstableHidden: function isUnstableHidden() {
            return hideUnstable;
        },
        updateUnstableButton: function () {
            var $unstableButton = $("#btn-unstable");
            $unstableButton.removeClass("btn-danger btn-success");
            if (hideUnstable) {
                $unstableButton.addClass("btn-success").text("");
            } else {
                $unstableButton.addClass("btn-danger").text("");
            }
        },
        dataTableInit: function ($tableElem) {
            var options = {};

            options.iFilterCol = 1;
            options.fnStateSaveParams = rtBuilders.saveState;
            options.fnStateLoadParams = rtBuilders.loadState;

            options.aoColumns = [
                {"mData": null, "sWidth": "7%", "sType": "string-ignore-empty"},
                {"mData": null, "sWidth": "13%", "sType": "natural"},
                {"mData": null, "sWidth": "10%", "sType": "numeric"},
                {"mData": null, "sWidth": "15%", "sType": "number-ignore-zero", "asSorting": ['desc','asc']},
                {"mData": null, "sWidth": "15%", "sType": "builder-status"},
                {"mData": null, "sWidth": "5%", "bSortable": false},
                {"mData": null, "sWidth": "15%", "bSortable": false},
                {"mData": null, "sWidth": "5%", "sType": numbersWithNA},
                {"mData": null, "sWidth": "5%", "bSortable": false}
            ];

            options.aaSorting = [
                [1, "asc"]
            ];

            options.aoColumnDefs = [
                rtTable.cell.builderTags(0, rtBuilders.filterTags),
                rtTable.cell.builderName(1, "txt-align-left"),
                rtTable.cell.buildProgress(2, false),
                rtTable.cell.buildLastRun(3),
                rtTable.cell.buildStatus(4, "latestBuild"),
                rtTable.cell.buildShortcuts(5, "latestBuild"),
                rtTable.cell.revision(6, function (data) {
                    if (data.latestBuild !== undefined) {
                        return data.latestBuild.sourceStamps;
                    }
                    return undefined;
                }, helpers.urlHasCodebases(), function getLatestRevDict() {
                    return latestRevDict;
                }),
                rtTable.cell.buildLength(7, function (data) {
                    if (data.latestBuild !== undefined) {
                        return data.latestBuild.times;
                    }
                    return undefined;
                }),
                {
                    "aTargets": [8],
                    "mRender": function (data, full, type) {
                        return hb.builders({customBuild: true, url: type.url, builderName: type.name});
                    },
                    "fnCreatedCell": function (nTd) {
                        var $nTd = $(nTd);
                        var $instantBuildBtn = $nTd.find(".instant-build");
                        popup.initRunBuildPopup($nTd.find(".custom-build"), $instantBuildBtn);
                    }
                }

            ];


            options.fnCreatedRow = function createRow(row, data, index) {
                // Add old-builds class to the row if the build is deemed old
                if (data.latestBuild !== undefined) {
                    if (helpers.isBuildOld(data.latestBuild)) {
                        $(row).addClass('old-build');
                    }
                }

            };

            return dt.initTable($tableElem, options);
        },
        noTag: NO_TAG,
        loadStateFromURL: function loadStateFromURL(oData) {
            var search = URI().search(true);

            if (search.tag) {
                savedTags = Array.isArray(search.tag) ? search.tag : [search.tag];
            } else {
                savedTags = [];
            }

            hideUnstable = search.hide_unstable === "true";
            rtBuilders.updateUnstableButton();
            rtBuilders.updateTagsForSelect2(false);

            if (oData && search.search) {
                oData.search = {search: search.search};
            } else if ($tbSorter && search.search) {
                $tbSorter.fnFilter(search.search);
                $searchField.val(search.search);
            } else if ($tbSorter) {
                $tbSorter.fnFilter("");
                $searchField.val("");
            }
        },
        saveStateToURL: helpers.debounce(function (search) {
            var url = URI(),
                tags = rtBuilders.getSelectedTags();

            url.setSearch({search: search, tag: tags});

            if (search.length === 0 || search === undefined) {
                url.removeSearch("search");
            }
            if (tags.length === 0) {
                url.removeSearch("tag");
            }
            if (((search !== undefined && search.length > 0) || tags.length > 0) || hideUnstable === true) {
                url.setSearch({hide_unstable: hideUnstable});
            }
            if ((search === undefined || search.length === 0) && tags.length === 0 && hideUnstable === false) {
                url.removeSearch("hide_unstable");
            }
            if (URI().search() !== url.search()) {
                window.history.pushState({path: url}, '', url);
            }
        }, 1000)
    };
    var numbersWithNA = $.fn.dataTable.absoluteOrder( [
            { value: 'N/A', position: 'bottom' }
    ] );

    return rtBuilders;
});
