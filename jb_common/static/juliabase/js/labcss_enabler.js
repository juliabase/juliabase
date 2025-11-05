$(document).ready( function () {
    // Define the list of table IDs to check
    var tableIdsToCheck = ["#five-chamber", 
                          "#six-chamber",   
                          "#cluster-tool-2", 
                          "#cluster-tool-1",  
                          "#dip-bench",        
                          "#hercules",          
                          "#jana",               
                                        
                          "#joseph",               
                          "#lada",                  
                          "#large-sputter",          
                          "#large-area",              
                          "#maria",                    
                          "#p-hot-wire",                
                          "#wetbench"]; // Add your table IDs here

    // Loop through each table ID
    tableIdsToCheck.forEach(function(tableId) {
        // Check if the table with the current ID exists
        if ($(tableId).length > 0) {
            // Import the CSS file if the table exists
            // Since JS is not processed server-side, then the static URL must be
            // declared in the HTML file, that is why we cannot explicitly write it
            // here instead of 'staticUrl'.
            $('head').append(`<link rel="stylesheet" type="text/css" href="${staticUrl}">`);
        }
    });
  } );
  