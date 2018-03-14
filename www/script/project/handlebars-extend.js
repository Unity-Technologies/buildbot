/*global define, Handlebars*/
define(function (require) {
    "use strict";

    var helpers = require('helpers'),
        KT = require('precompiled.handlebars');

    require('handlebars');

    function registerHelpers() {
        var healthNames = ["good", "warning", "bad"];

        Handlebars.registerHelper('slave:healthClass', function () {
            return healthNames[-this.health];
        });

        Handlebars.registerHelper('buildCSSClass', function (value) {
            return helpers.getCssClassFromStatus(value);
        });

        Handlebars.registerHelper('eachByStatus', function (array, key, opts) {
            return helpers.sortByStatus(array, key, opts);
        });
    }
    registerHelpers();
    return KT;
});