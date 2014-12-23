// This file is part of JuliaBase, the samples database.
//
// This file is part of JuliaBase, see http://www.juliabase.org.
// Copyright © 2008–2015 Torsten Bronger <bronger@physik.rwth-aachen.de>,
//                       Marvin Goblet <m.goblet@fz-juelich.de>.
//
// This program is free software: you can redistribute it and/or modify it under
// the terms of the GNU Affero General Public License as published by the Free
// Software Foundation, either version 3 of the License, or (at your option) any
// later version.
//
// This program is distributed in the hope that it will be useful, but WITHOUT
// ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
// FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
// details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.


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
