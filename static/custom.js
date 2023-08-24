function replace_div_alert(container_div){
    const alertString = gettext('Error while loading data');
    $(container_div).html('<div class="alert alert-warning" role="alert">' + alertString + '</div>');
}

function replace_div_nodata(container_div){
    const nodataString = gettext('No data available');
    $(container_div).html('<div class="alert alert-primary" role="alert">' + nodataString + '</div>');
}

function loadGraph(container, url){
    var container_div = '#' + container;
    const loadingString = gettext('Loading...');
    $(container_div).html('<div class="spinner-border m-5 justify-content-center" role="status"><span class="sr-only">' + loadingString + '</span></div>');

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
                    if(content['layout']['margin'] == undefined){
                        // set a default margin
                        content['layout']['margin'] = {l: 80, r: 0, b: 50, t: 50, pad: 0};
                    }
                    Plotly.newPlot(container, content['data'], content['layout']);
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