(function() {
    // Wait for jQuery to be available
    function waitForJQuery(callback) {
        if (typeof jQuery !== 'undefined') {
            callback(jQuery);
        } else {
            setTimeout(function() { waitForJQuery(callback); }, 50);
        }
    }

    waitForJQuery(function($) {
        function waitForDataTables(callback) {
            if (typeof $.fn.DataTable !== 'undefined') {
                callback();
            } else {
                var attempts = 0;
                var checkInterval = setInterval(function() {
                    attempts++;
                    if (typeof $.fn.DataTable !== 'undefined') {
                        clearInterval(checkInterval);
                        callback();
                    } else if (attempts > 200) { // 10 seconds timeout
                        clearInterval(checkInterval);
                        console.error('lab_notebook.js (juliabase): DataTables failed to load after 10 seconds');
                    }
                }, 50);
            }
        }

        $(function () {
            waitForDataTables(initLabNotebook);
        });

        function initLabNotebook() {
        //Dictionary full of all the strings from datatables that need to be translated
        var langDict = {
            processing:     gettext("Processing..."),
            search:         gettext("Search&nbsp;:"),
            lengthMenu:     gettext("Show _MENU_ entries"),
        info:           gettext("Showing _START_ to _END_ of total _TOTAL_ entries"),
        infoEmpty:      gettext("Showing 0 to 0 of total 0 entries"),
        infoFiltered:   gettext("(filtered from total _MAX_ entries)"),
        infoPostFix:    "",
        loadingRecords: gettext("Loading records..."),
        zeroRecords:    gettext("No entries found"),
        emptyTable:     gettext("No data available"),
        aria: {
            sortAscending:  gettext(": activate to sort column ascending"),
            sortDescending: gettext(": activate to sort column descending")
        }
    };
    
    // Initialize datatables for all the tables of class "lab-notebook"
    // EXCEPT the ones with class "manual-datatable".
    $('.lab-notebook:not(.manual-datatable)').DataTable({
        order: [],
        // pageLength: 50,
        scrollX: true,
        scrollY: '50vh',
        language: langDict,
        fixedColumns: true,
        fixedHeader: true // Enable FixedHeader extension
    });
    
    try{
        if(no_bs5 == false){
            
        }
    } catch(error){
        // Use jQuery to select the specific div and find its child table element
        var $table = $('.lock-header').find('table');
    
        // Add new classes to the table element
        $table.addClass('lab-notebook table table table-hover table-bordered table-striped-columns');

        // Preserve existing classes by ensuring they are not already present
        var existingClasses = $table.attr('class').split(' ');
        existingClasses.forEach(function(className) {
            if (!$table.hasClass(className)) {
                $table.addClass(className);
            }
        });

        // Find the thead element within the table and add new classes to it
        $table.find('thead').addClass('align-middle');
    }
    } // end initLabNotebook
    }); // end waitForJQuery callback
})();