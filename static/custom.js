function replace_div_alert(container_div){
    $(container_div).html('<div class="alert alert-warning" role="alert">Could not load this graph</div>');
}

function loadGraph(container, url){
    var container_div = '#' + container;
    $(container_div).html('<div class="spinner-border m-5 justify-content-center" role="status"><span class="sr-only">Loading...</span></div>');

    $.ajax({
        url : url,
        type : 'GET',
        tryCount : 0,
        retryLimit : 3,
        dataType    : 'json',
        contentType : 'application/json',
        success : function(data) {
            $(container_div).html('');
            Plotly.newPlot(container, data['lines'], data['layout']);
        },
        error : function(xhr, textStatus, errorThrown ) {
            console.log(textStatus);
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