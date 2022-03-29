function loadGraph(container, url){
    var container_div = '#' + container;
    $(container_div).html('<div class="spinner-border m-5 justify-content-center" role="status"><span class="sr-only">Loading...</span></div>');
    $.getJSON(url, function(data){
      $(container_div).html('');
      Plotly.newPlot(container, data['lines'], data['layout']);
    });
}