define(["screensize","helpers"],function(e,t){var n;return n={init:function(){$(window).resize(function(){e.isLargeScreen()||$(".project-dropdown-js").remove(),e.isLargeScreen()&&$(".submenu").remove()}),$(".smartphone-nav").click(function(){$(".top-menu").is(":hidden")?$(".top-menu").addClass("show-topmenu"):$(".top-menu").removeClass("show-topmenu")}),$("#projectDropdown").click(function(n){var r=$(".submenu"),i='<div id="bowlG"><div id="bowl_ringG"><div class="ball_holderG"><div class="ballG"></div></div></div></div>';$("body").append(i).show();var s="/projects";if(e.isLargeScreen()){var o=$('<div class="more-info-box project-dropdown-js"><span class="close-btn"></span><h3>Builders shorcut</h3><div id="content1"></div></div>');$(o).insertAfter($(this))}else if(r.length){r.add("#bowlG").remove();return}$.get(s).done(function(n){var r=$(n);$("#bowlG").remove();if(e.isLargeScreen()){var i=$(r).find(".tablesorter-js");$(i).appendTo($("#content1")),$(".tablesorter-js",o).removeClass("tablesorter"),$(".top-menu .shortcut-js .scLink").each(function(){var e=$(this).attr("data-sc");$(this).attr("href",e)}),$(o).slideDown("fast")}else{var i=$(r).find(".scLink");$("<ul/>").addClass("submenu").appendTo(".project-dropdown"),$(i).each(function(){var e=$(this).attr("data-sc");$(this).attr("href",e);var t=$("<li>").append($(this));$(".submenu").append(t)}),$(".submenu").show().attr("style","")}e.isLargeScreen()&&($(".submenu").remove(),t.closePopup(o,"slideUp"))})})}},n});