$(document).ready( function () {

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
        // We use this to initialize datatables for all the tables of class "lab-notebook"
        // EXCEPT the ones written after ":not". Some of those tables do not work properly
        // with datatables. Some others are here like "screenprinter" that need to be initialized
        // separately to add custom features. Each time you want a table to have special features,
        // add it here. 
        // The backslash is here used to return to line and increase code readability.
        $('.lab-notebook:not(#screenprinter,\
                            #five-chamber,   \
                            #six-chamber,     \
                            #cluster-tool-2,   \
                            #cluster-tool-1,    \
                            #dip-bench,          \
                            #hercules,            \
                            #jana,                 \
                            #joseph,                \
                            #lada,                   \
                            #large-sputter,           \
                            #large-area,               \
                            #maria,                     \
                            #p-hot-wire,                 \
                            #wetbench,                    \
                            #screenprinter-paste,          \
                            #screenprinter-screen)').DataTable({
            order: [],
            pageLength: 50,
            scrollX: true,
            language: langDict,
        fixedColumns: true,
        fixedHeader: true // Enable FixedHeader extension
        }); // Initialize the DataTables for the rest of the tables with the class "lab-notebook"


        // Custom table declaration for the table with the id "screenprinter-paste" 
        $('#screenprinter-paste').DataTable({

            createdRow: function (row, data, dataIndex){
                  // FIXME: This is quite a terrible way to pick a column, since new columns can be added
                  // and the current setting will break if not fixed. Use column name instead of number
                  if(data[11] === "True"){
                    // You wanna know why I am using the "table-danger" class instead
                    // of simply changing the color of the row directly?
                    // Well, Bootstrap loves overriding everything. Might aswell use
                    // its classes instead. 
                    $(row).addClass('table-danger');
                  }
              },
                order: [],
                pageLength: 50,
                scrollX: true,
                language: langDict,
                fixedColumns: true,
                fixedHeader: true // Enable FixedHeader extension
                }); // Initialize the DataTables for the rest of the tables with the class "lab-notebook"
                  
  
        $('#screenprinter-screen').DataTable({
  
            createdRow: function (row, data, dataIndex){
                  // FIXME: This is quite a terrible way to pick a column, since new columns can be added
                  // and the current setting will break if not fixed. Use column name instead of number
                  if(data[15] === ""){
                    // You wanna know why I am using the "table-danger" class instead
                    // of simply changing the color of the row directly?
                    // Well, Bootstrap loves overriding everything. Might aswell use
                    // its classes instead. 
                    $(row).addClass('table-danger');
                  }
              },
                order: [],
                pageLength: 50,
                scrollX: true,
                language: langDict,
                fixedColumns: true,
                fixedHeader: true // Enable FixedHeader extension
                }); // Initialize the DataTables for the rest of the tables with the class "lab-notebook"
      

        $('#screenprinter').DataTable( {
            language: langDict,
            order: [],
            pageLength: 50,
            scrollX: true,
            fixedColumns: true,
            fixedHeader: true, // Enable FixedHeader extension
            columnDefs: [ {
                targets: [ 2, 4, 6 ], // Assuming the column index is 0
                render: function (data, type, row) {
                    if (data === "None") {
                        return "<i>None</i>"; // Convert "None" to null for proper sorting
                    }
                    // Extract numeric part of the string after 'S'
                    // FIXME: Temporary solution, since this regex pattern does not 
                    // take into account strings that start with a lower case
                    var matches = data.match(/\d+/i);
                    // That is why we turn the first character of all 
                    // the strings to upper case
                    data = data.charAt(0).toUpperCase() + data.slice(1);

                    // Check if there are strings that match the pattern
                    if (matches !== null) {
                        // If yes, take the number
                        var num = matches[0];
                        // If the number has only one digit, pad a zero at the beginning
                        // to sort things properly (i.e. S7 becomes S07) 
                        if (num.length === 1) {
                            let extracted = data.substring(0, data.indexOf(num));
                            num = '0' + num; // pad a zero at the beginning
                            // Check if there isn't anything attached to the number
                            if (/^\d+$/.test(data.charAt(-1)) === false){
                                // If yes attach back all the things the number starts and ends with
                                return extracted + num + data.slice(num.length);
                            }
                            // If not just return the beginning of the string and number
                            return extracted + num;
                        }
                        // If the number has more than one digit, you can simply return it
                        return data;
                    } else {
                        return data; // return 0 if no number is found
                    }
                },
                type: 'numeric'
            } ]
        } ); 

        // Custom initialization for "manual-cleaning" where the entries are sorted in descending
        // order as asked by Dorothea
        // $('#manual-cleaning').DataTable({
        //     order: [[ 0, "desc" ]],
        //     scrollX: true,
        //     language: langDict,
        //     fixedColumns: true,
        //     fixedHeader: true // Enable FixedHeader extension
        //     }); // Initialize the DataTables for the rest of the tables with the class "lab-notebook"
                  
        
    }, 1000);
    

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

    // Check if the URL contains a specific substring
    // We use this to get rid of the date form for screenprinter paste and screen
    if (window.location.href.indexOf('screenprinter_paste') > -1 || window.location.href.indexOf('screenprinter_screen') > -1) {
        // Hide the form with id="date-form"
        console.log('Substring found! Hiding date form.');
        $('#date-form').hide();
    }
  } );