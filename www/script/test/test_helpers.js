/*global define, describe, it, expect, beforeEach, afterEach*/
define(["jquery", "helpers"], function ($, helpers) {
  "use strict";

  describe("A build", function () {

    var now = new Date(),
      build = {
        times: []
      };

    helpers.settings = function () {
      return {oldBuildDays: 7}
    };

    it("is old", function () {
      build.times = [new Date().setDate(now.getDate() - 8) / 1000.0];
      expect(helpers.isBuildOld(build)).toBeTruthy();

      build.times = [new Date().setDate(now.getDate() - 50) / 1000.0];
      expect(helpers.isBuildOld(build)).toBeTruthy();
    });

    it("is new", function () {
      build.times = [new Date().setDate(now.getDate() - 1) / 1000.0];
      expect(helpers.isBuildOld(build)).toBeFalsy();

      build.times = [new Date().setDate(now.getDate() - 3) / 1000.0];
      expect(helpers.isBuildOld(build)).toBeFalsy();
    });

  });

  describe("A project builders history", function () {
    
    it("is saved if local storage is accessible", function () {
      var key = 'testhistorylist'
      helpers.updateBuildersHistoryList(key, 100);
      expect(window.localStorage.getItem(key)).toBe('100');

      helpers.updateBuildersHistoryList(key, 102);
      expect(window.localStorage.getItem(key)).toBe('102');
    });
    
    it("list is empty if localStorage is not accessible", function () {
      var key = 'testhistorylist1'
      spyOn(window, "localStorage").and.callFake(function() {
        throw {
          name: 'System Error',
        };
      });

      var list = helpers.getBuildersHistoryList(key);
      expect(list).toEqual([]);
    });

    it("item is not removed from local storage if local storage is full", function () {
      var key = 'testhistorylist2'
      helpers.updateBuildersHistoryList(key, 100);

      window.localStorage.setItem = function () {
        throw {
          code: 22
        };
      }
      helpers.updateBuildersHistoryList(key, 102);
      expect(window.localStorage.getItem(key)).toBeNull();

      window.localStorage.setItem = function () {
        throw {
          code: 1014,
          name: NS_ERROR_DOM_QUOTA_REACHED,
        };
      }
      helpers.updateBuildersHistoryList(key, 10);
      expect(window.localStorage.getItem(key)).toBeNull();

      window.localStorage.setItem = function () {
        throw {
          number: -2147024882
        };
      }

      helpers.updateBuildersHistoryList(key, 10);
      expect(window.localStorage.getItem(key)).toBeNull();

    });

  });

  describe("A sort function by status", function () {

    beforeEach(function() {
      var RUNNING = -1,
          SUCCESS = 0,
          WARNINGS = 1,
          FAILURE = 2,
          EXCEPTION = 4,
          WAITING_FOR_DEPENDENCY = 9;

      this.input_object_by_results_as_list = {
        "Simple Test #1": {url: '1', results: [SUCCESS]},
        "Simple Test #2": {url: '2', results: [WARNINGS]},
        "Simple Test #3": {url: '3', results: [SUCCESS]},
        "Simple Test #4": {url: '4', results: [WAITING_FOR_DEPENDENCY]},
      };

      this.input_object_by_order_as_list = {
        "Simple Test #1": {url: '1', order: [SUCCESS]},
        "Simple Test #2": {url: '2', order: [WARNINGS]},
        "Simple Test #3": {url: '3', order: [SUCCESS]},
        "Simple Test #4": {url: '4', order: [WAITING_FOR_DEPENDENCY]},
      };

      this.input_object_by_result = {
        "Simple Test #1": {url: '1', results: SUCCESS},
        "Simple Test #2": {url: '2', results: WARNINGS},
        "Simple Test #3": {url: '3', results: SUCCESS},
        "Simple Test #4": {url: '4', results: WAITING_FOR_DEPENDENCY},
      };

      this.input_object_without_results = {
        "Simple Test #1": {url: '1'},
        "Simple Test #2": {url: '2'},
        "Simple Test #3": {url: '3'},
        "Simple Test #4": {url: '4'},
      };

      this.opts_stub = {
        'fn': function(item, data) {
          return item.url + '\n';
        },
      };

    });
    it("sort result passed as object by 'results' key as list of integer value", function() {
      var ret = helpers.sortByStatus(this.input_object_by_results_as_list, 'results', this.opts_stub);

      var expected_value = '4\n1\n3\n2\n';
      expect(ret).toBe(expected_value);
    });

    it("sort result passed as object by 'order' key", function() {
      var ret = helpers.sortByStatus(this.input_object_by_order_as_list, 'order', this.opts_stub);

      var expected_value = '4\n1\n3\n2\n';
      expect(ret).toBe(expected_value);
    });

    it("sort result passed as object by 'results' key as integer value", function() {
      var ret = helpers.sortByStatus(this.input_object_by_result, 'results', this.opts_stub);

      var expected_value = '4\n1\n3\n2\n';
      expect(ret).toBe(expected_value);
    });

    it("sort result passed as object without results", function() {
      var ret = helpers.sortByStatus(this.input_object_without_results, 'results', this.opts_stub);

      var expected_value = '1\n2\n3\n4\n';
      expect(ret).toBe(expected_value);
    });
  });

});
