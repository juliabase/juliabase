// This file is part of JuliaBase, the samples database.
//
// Copyright (C) 2011 Forschungszentrum Jülich, Germany,
//                    Marvin Goblet <m.goblet@fz-juelich.de>,
//                    Torsten Bronger <t.bronger@fz-juelich.de>
//
// You must not use, install, pass on, offer, sell, analyse, modify, or distribute
// this software without explicit permission of the copyright holder.  If you have
// received a copy of this software without the explicit permission of the
// copyright holder, you must destroy it immediately and completely.


var juliabase = {};

juliabase.debug = false;

juliabase.JuliaBaseError = function(message, number) {
    this.name = "JuliaBaseError";
    this.message = message;
    this.number = number;
};
juliabase.JuliaBaseError.prototype = new Error();

juliabase.request = function(url, success, data, type) {
    var parameters = {url: url, dataType: "json", success: success, type: type, data: data};
    parameters.error = function(response) {
	var error_data = $.parseJSON(response.responseText);
	var error_code = error_data[0];
	var error_message = "Juliabase error #" + error_code + ": " + error_data[1];
        if (juliabase.debug) alert(error_message);
	throw new juliabase.JuliaBaseError(error_message, error_code);
    }
    $.ajax(parameters);
};
