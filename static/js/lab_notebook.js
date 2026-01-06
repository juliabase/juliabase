$(document).ready(function () {
    // Add manual-datatable class to tables that should not be auto-initialized by juliabase
    var manualTables = [
        '#screenprinter',
        '#five-chamber',
        '#six-chamber',
        '#cluster-tool-2',
        '#cluster-tool-1',
        '#dip-bench',
        '#hercules',
        '#jana',
        '#joseph',
        '#lada',
        '#large-sputter',
        '#large-area',
        '#maria',
        '#p-hot-wire',
        '#wetbench',
        '#screenprinter-paste',
        '#screenprinter-screen',
        '#experiment'
    ];
    $(manualTables.join(', ')).addClass('manual-datatable');
    
    // Define langDict for DataTables (copied from juliabase)
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

    // Specific initializations moved from juliabase
    $('#experiment').DataTable({
            initComplete: function () {
                var api = this.api();
                setTimeout(function() {
                    api.columns.adjust().draw();
                }, 200);
            },
            order: [],
            scrollX: true,
            scrollY: '50vh',
            fixedColumns: true,
            fixedHeader: true,
            columnDefs: [
                {
                    targets: '_all', // Apply to all columns except the first one
                    render: function (data, type, row, meta) {
                        // Ignore rendering for the first column
                        // if (meta.col === 0) return data;
        
                        if (type === 'display') {
                            // Create a temporary element to parse the HTML
                            var div = document.createElement('div');
                            div.innerHTML = data;
        
                            // Check if the content contains a link
                            var link = div.querySelector('a');
                            if (link) {
                                // Extract the URL and the visible text
                                var url = link.href;
                                var text = link.textContent || link.innerText || "";
        
                                // Truncate the visible text if it's too long
                                if (text.length > 30) {
                                    text = text.substr(0, 30) + '...';
                                }
        
                                // Rebuild the anchor tag with the original URL and truncated text
                                return `<a href="${url}" title="${link.textContent}">${text}</a>`;
                            } else {
                                // If no link, just truncate the text
                                var text = div.textContent || div.innerText || "";
                                if (text.length > 30) {
                                    text = text.substr(0, 30) + '...';
                                }
                                return `<div title="${div.textContent}">${text}</div>`;
                            }
                        }
                        return data;
                    }
                }
            ],
        });
        

        // Custom table declaration for the table with the id "screenprinter-paste" 
        $('#screenprinter-paste').DataTable({
            initComplete: function () {
                var api = this.api();
                setTimeout(function() {
                    api.columns.adjust().draw();
                }, 200);
            },

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
                // pageLength: 50,
                scrollX: true,
                scrollY: '50vh',
                language: langDict,
                fixedColumns: true,
                fixedHeader: true // Enable FixedHeader extension
                }); // Initialize the DataTables for the rest of the tables with the class "lab-notebook"
                  
  
        $('#screenprinter-screen').DataTable({
            initComplete: function () {
                var api = this.api();
                setTimeout(function() {
                    api.columns.adjust().draw();
                }, 200);
            },
  
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
                // pageLength: 50,
                scrollY: '50vh',
                scrollX: true,
                language: langDict,
                fixedColumns: true,
                fixedHeader: true // Enable FixedHeader extension
                }); // Initialize the DataTables for the rest of the tables with the class "lab-notebook" 

        $('#screenprinter').DataTable( {
            initComplete: function () {
                var api = this.api();
                setTimeout(function() {
                    api.columns.adjust().draw();
                }, 200);
            },
            
            language: langDict,
            order: [],
            // pageLength: 50,
            scrollX: true,
            scrollY: '50vh',
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

});