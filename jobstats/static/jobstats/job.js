const formatter = new Intl.NumberFormat('en-CA', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  $.ajax({
    url : 'value/cost.json',
    type : 'GET',
    tryCount : 0,
    retryLimit : 3,
    dataType    : 'json',
    contentType : 'application/json',
    success : function(data) {
      if(data.kwh) {
        $('#energy').html(formatter.format(data.kwh) + ' kWh');
      }

      if(data.electric_car_range_km){
        const teslaString = gettext('Based on the efficiency of a Tesla Model 3');
        $('#car_range').html('<a href="#" data-toggle="tooltip" title="' + teslaString +'">' + formatter.format(data.electric_car_range_km) + ' km </a>');
      }

      if(data.co2_emissions_kg) {
        $('#co2').html(formatter.format(data.co2_emissions_kg * 1000) + ' g');
      }

      if(data.electricity_cost_dollar && data.cooling_cost_dollar && data.hardware_cost_dollar){
        const cost_format = gettext('Electricity: %s $ <br /> Cooling: %s $ <br /> <a href="#" data-toggle="tooltip" title="Amortized over %s years"> Hardware:</a> %s $ <br /> Total: %s $')
        $('#cost').html(interpolate(cost_format, [
          formatter.format(data.electricity_cost_dollar),
          formatter.format(data.cooling_cost_dollar),
          data.amortization_years,
          formatter.format(data.hardware_cost_dollar),
          formatter.format(data.electricity_cost_dollar + data.cooling_cost_dollar + data.hardware_cost_dollar)]));
      }

      if(data.cloud_cost_dollar){
        $('#cloud').html('<a href="#" data-toggle="tooltip" title="' + gettext('Based on the price of c6a.16xlarge and g5.12xlarge') + '">' + gettext('On-Demand instance') + ':</a> ' +formatter.format(data.cloud_cost_dollar) + ' $');
      }
      $('[data-toggle="tooltip"]').tooltip();
    },
    error : function(xhr, textStatus, errorThrown ) {
      if (textStatus == 'timeout' || textStatus == 'error') {
        this.tryCount++;
        if (this.tryCount <= this.retryLimit) {
            //try again
            $.ajax(this);
            return;
        }
      }
      const nodataString = gettext('No data');
      $('#energy').html(nodataString);
      $('#car_range').html(nodataString);
      $('#co2').html(nodataString);
      $('#cost').html(nodataString);
      $('#cloud').html(nodataString);
    }
  });
