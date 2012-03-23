// This file is part of Chantal, the samples database.
//
// Copyright (C) 2011 Forschungszentrum Jülich, Germany,
//                    Marvin Goblet <m.goblet@fz-juelich.de>,
//                    Torsten Bronger <t.bronger@fz-juelich.de>
//
// You must not use, install, pass on, offer, sell, analyse, modify, or distribute
// this software without explicit permission of the copyright holder.  If you have
// received a copy of this software without the explicit permission of the
// copyright holder, you must destroy it immediately and completely.


var chantal = {};

chantal.debug = false;

chantal.ChantalError = function(message, number) {
    this.name = "ChantalError";
    this.message = message;
    this.number = number;
};
chantal.ChantalError.prototype = new Error();

chantal.request = function(url, success, data, type) {
    var parameters = {url: url, dataType: "json", success: success, type: type, data: data};
    parameters.error = function(response) {
	var error_data = $.parseJSON(response.responseText);
	var error_code = error_data[0];
	var error_message = "Chantal error #" + error_code + ": " + error_data[1];
        if (chantal.debug) alert(error_message);
	throw new chantal.ChantalError(error_message, error_code);
    }
    $.ajax(parameters);
};
