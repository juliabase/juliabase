// $(document).ready(function () {
//     // Function to sort the table
//     function sortTable(columnIndex) {
//         var table, rows, switching, i, x, y, shouldSwitch, dir, switchcount = 0;
//         table = document.querySelector('.lab-notebook');
//         switching = true;
//         // Set the sorting direction to ascending
//         dir = "asc";

//         while (switching) {
//             switching = false;
//             rows = table.rows;

//             for (i = 1; i < (rows.length - 1); i++) {
//                 shouldSwitch = false;
//                 x = parseFloat(rows[i].getElementsByTagName("td")[columnIndex].innerHTML.replace(/[^0-9.-]+/g,""));
//                 y = parseFloat(rows[i + 1].getElementsByTagName("td")[columnIndex].innerHTML.replace(/[^0-9.-]+/g,""));

//                 if (dir === "asc") {
//                     if (x > y) {
//                         shouldSwitch = true;
//                         break;
//                     }
//                 } else if (dir === "desc") {
//                     if (x < y) {
//                         shouldSwitch = true;
//                         break;
//                     }
//                 }
//             }

//             if (shouldSwitch) {
//                 rows[i].parentNode.insertBefore(rows[i + 1], rows[i]);
//                 switching = true;
//                 switchcount++;
//             } else {
//                 if (switchcount === 0 && dir === "asc") {
//                     dir = "desc";
//                     switching = true;
//                 }
//             }
//         }
//     }

//     // Event listener for column headers
//     $(".lab-notebook th").click(function () {
//         var columnIndex = $(this).index();
//         sortTable(columnIndex);
//     });
// });

// import DataTable from 'datatables.net-dt';
// import 'datatables.net-responsive-dt';
 
// let table = new DataTable('#lab-notebook', {
//     responsive: true
// });

// $(document).ready( function () {
//     $('#lab-notebook').DataTable();
// } );

import * as DataTable from 'https://cdn.datatables.net/1.13.7/js/jquery.dataTables.js';
import * as responsive from 'https://cdn.datatables.net/responsive/2.2.9/js/dataTables.responsive.js';

let table = new DataTable('#lab-notebook', {
    responsive: true
});

$(document).ready( function () {
    $('#lab-notebook').DataTable();
} );