define(["datatables-plugin","helpers","libs/natural-sort","popup"],function(e,t,n){var r;return r={init:function(){r.initSortNatural(),$.extend($.fn.dataTable.defaults,{bPaginate:!1,bLengthChange:!1,bFilter:!1,bSort:!0,bInfo:!1,bAutoWidth:!1,sDom:'<"table-wrapper"t>',bRetrieve:!0,asSorting:!0,bServerSide:!1,bSearchable:!0,aaSorting:[],iDisplayLength:50,bStateSave:!0})},initTable:function(e,t){e.hasClass("input-js")&&(t.bFilter=!0,t.oLanguage={sSearch:""},t.sDom='<"top"flip><"table-wrapper"t><"bottom"pi>'),e.hasClass("tools-js")&&(t.bPaginate=!0,t.bLengthChange=!0,t.bInfo=!0,t.bFilter=!0,t.oLanguage={sSearch:"",sLengthMenu:'Entries per page<select><option value="10">10</option><option value="25">25</option><option value="50">50</option><option value="100">100</option><option value="-1">All</option></select>'},t.sDom='<"top"flip><"table-wrapper"t><"bottom"pi>');var n=undefined,r=e.attr("data-default-sort-dir")||"asc";e.attr("data-default-sort-col")!==undefined&&(n=parseInt(e.attr("data-default-sort-col")),t.aaSorting=[[n,r]]);if(t.aoColumns===undefined){var i=[];$("> thead th",e).each(function(e,t){$(t).hasClass("no-tablesorter-js")?i.push({bSortable:!1}):n!==undefined&&n===e?i.push({sType:"natural"}):i.push(null)}),t.aoColumns=i}else i=t.aoColumns,$("> thead th",e).each(function(e,t){$(t).hasClass("no-tablesorter-js")&&i[e].bSortable===undefined?i[e].bSortable=!1:i[e].bSortable===undefined&&(i[e].bSortable=!0),n!==undefined&&n===e&&(i[e].sType="natural")}),t.aoColumns=i;e.hasClass("branches-selectors-js")&&t.sDom===undefined&&(t.sDom='<"top"flip><"table-wrapper"t><"bottom"pi>');var s=e.dataTable(t),o=$(".dataTables_filter input").attr("placeholder","Filter results");return $("body").keyup(function(e){e.which===70&&o.focus()}),s},initSortNatural:function(){jQuery.extend(jQuery.fn.dataTableExt.oSort,{"natural-pre":function(e){try{return e=$(e).text().trim(),e}catch(t){return e}},"natural-asc":function(e,t){return n.sort(e,t)},"natural-desc":function(e,t){return n.sort(e,t)*-1}})}},r});