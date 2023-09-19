function replace_div_alert(container_div){
    const alertString = gettext('Error while loading data');
    $(container_div).html('<div class="alert alert-warning" role="alert">' + alertString + '</div>');
}

function replace_div_nodata(container_div){
    const nodataString = gettext('No data available');
    $(container_div).html('<div class="alert alert-primary" role="alert">' + nodataString + '</div>');
}

var debounce_loadGraph = _.debounce(function(container, url){
    loadGraph(container, url);
}, 100);

function loadGraph(container, url){
    var container_div = '#' + container;
    const loadingString = gettext('Loading...');
    //if content of div is empty, show loading spinner
    if($('#' + container).html().trim().length == 0){
        $(container_div).html('<div class="spinner-border m-5 justify-content-center" role="status"><span class="sr-only">' + loadingString + '</span></div>');
    }

    $.ajax({
        url : url,
        type : 'GET',
        tryCount : 0,
        retryLimit : 3,
        dataType    : 'json',
        contentType : 'application/json',
        success : function(content) {
            if(content['data']){
                if(content['data'].length == 0){
                    replace_div_nodata(container_div);
                }
                else{
                    $(container_div).html('');
                    if(content['layout'] == undefined){
                        content['layout'] = {};
                    }
                    if(content['layout']['margin'] == undefined){
                        // set a default margin
                        content['layout']['margin'] = {l: 80, r: 0, b: 50, t: 50, pad: 0};
                    }

                    if(content['config'] == undefined) {
                        content['config'] = {};
                    }

                    Plotly.newPlot(container, content['data'], content['layout'], content['config']);

                    $(container_div).on('plotly_relayout', function(self, relayout_data){
                        var end_date = new Date(relayout_data['xaxis.range[1]']);
                        var end_date_unix = Math.round(end_date.getTime() / 1000);

                        var start_date = new Date(relayout_data['xaxis.range[0]']);
                        var start_date_unix = Math.round(start_date.getTime() / 1000);

                        // remove the old parameters from the url string
                        var url_splitted = url.split('?');
                        url = url_splitted[0];

                        // get the new range and reload the graph
                        var newurl = url + '?start=' + start_date_unix + '&end=' + end_date_unix;
                        debounce_loadGraph(container, newurl);
                    });
                }
            }
        },
        error : function(xhr, textStatus, errorThrown ) {
            if (textStatus == 'timeout' || textStatus == 'error') {
                this.tryCount++;
                if (this.tryCount <= this.retryLimit) {
                    //try again
                    $.ajax(this);
                    return;
                }
                replace_div_alert(container_div);
                return;
            }
            if (xhr.status == 500) {
                replace_div_alert(container_div);
            } else {
                replace_div_alert(container_div);
            }
        }
    });
}