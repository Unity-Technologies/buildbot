require.config({
	paths: {
		'jquery': 'libs/jQuery-2-0-3',
		'selectors':'project/selectors',
		'select2': 'plugins/select2',
		'datatables-plugin': 'plugins/jquery-datatables',
		'dataTables': 'project/dataTables',
		'dotdotdot': 'plugins/jquery-dotdotdot',
		'screensize': 'project/screen-size',
		'currentitem': 'project/set-current-item',
		'helpers': 'project/helpers',
		'projectdropdown': 'project/project-drop-down',
		'popup': 'project/popup',
		'realtime': 'project/realtime',
		'jqache': 'plugins/jqache-0-1-1-min'
	}
});

require(['jquery','popup','screensize','projectdropdown','helpers'], 
	function($, popup, screenSize, projectDropDown, helpers ) {
	'use strict';

	$(document).ready(function() {
		
		
		if ($('.tablesorter-js').length > 0) {
			require(['dataTables'],
	        function(dataTables) {
	        	dataTables.init();
	        });
		}
 	
		if (helpers.getCurrentPage('isrealtime') && $('body').attr('data-realTimeServer') != '') {			
			require(['realtime', 'jqache'],
	        function(realtime) {
	        	realtime.init();
	        });
		}

		// tooltip for long txtstrings
		if ($('.ellipsis-js').length) {
			require(['dotdotdot'],
	        function(dotdotdot) {
	        	$(".ellipsis-js").dotdotdot();
	        });
		}

		// codebases combobox selector
		if ($('#commonBranch_select').length || $('.select-tools-js').length) {
			require(['selectors'],
		        function(selectors) {
			        selectors.comboBox('.select-tools-js');	
			        selectors.init();
		    });
		}
		if ($('#builddetail_page').length > 0) {
			helpers.summaryArtifactTests();
		}
				
		// get scripts for general popups
		popup.init();
		// get scripts for the projects dropdown
		projectDropDown.init();
		// get all common scripts
		helpers.init();	

	});
});