$(document).ready( function () {
    console.log("zldxplord");
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

    
    // We use a timer here to allow everything to load before calling datatables.
    // This might not be necessary if 
    setTimeout(function() {
        $('.lab-notebook').DataTable({
                order: [],
                // pageLength: 50,
                scrollX: true,
                scrollY: '50vh',
                language: langDict,
            fixedColumns: true,
            fixedHeader: true // Enable FixedHeader extension
        }); // Initialize the DataTables for the rest of the tables with the class "lab-notebook"
    }, 1000);
  } );