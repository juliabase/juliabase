/*
 * This file is part of JuliaBase, see http://www.juliabase.org.
 * Copyright © 2008–2015 Forschungszentrum Jülich GmbH, Jülich, Germany
 *
 * This program is free software: you can redistribute it and/or modify it under
 * the terms of the GNU Affero General Public License as published by the Free
 * Software Foundation, either version 3 of the License, or (at your option) any
 * later version.
 */

$(function() {
    $('form[method="get"]').submit(function(event) {
        var $target = $(event.target);
        $target.find("input:not(.submit-always),select:not(.submit-always),textarea:not(.submit-always)").each(function() {
            if ($(this).val() == "") {
                $(this).prop("disabled", true);
            }
        });
    });
});
