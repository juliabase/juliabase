$(document).ready( function () {
    // Define the list of table IDs to check
    var tableIdsToCheck = ["#five-chamber", 
                          "#six-chamber",   
                          "#cluster-tool-2", 
                          "#cluster-tool-1",  
                          "#dip-bench",        
                          "#hercules",          
                          "#jana",               
                          "#jopes",               
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
            $('head').append(`<link rel="stylesheet" type="text/css" href="{% static 'juliabase/css/labcss.css' %}">`);
        }
    });
  } );