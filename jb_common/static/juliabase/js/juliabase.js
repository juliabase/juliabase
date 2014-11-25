// This file is part of JuliaBase, the samples database.
//
// Copyright © 2008–2014 Forschungszentrum Jülich, Germany,
//                       Marvin Goblet <m.goblet@fz-juelich.de>,
//                       Torsten Bronger <t.bronger@fz-juelich.de>
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

function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie != '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = jQuery.trim(cookies[i]);
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) == (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
var csrftoken = getCookie('csrftoken');
function csrfSafeMethod(method) {
    // these HTTP methods do not require CSRF protection
    return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
}
$.ajaxSetup({
    beforeSend: function(xhr, settings) {
        if (!csrfSafeMethod(settings.type) && !this.crossDomain) {
            xhr.setRequestHeader("X-CSRFToken", csrftoken);
        }
    }
});
