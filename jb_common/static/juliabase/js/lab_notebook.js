import * as DataTable from 'https://cdn.datatables.net/1.13.7/js/jquery.dataTables.js';
import * as responsive from 'https://cdn.datatables.net/responsive/2.2.9/js/dataTables.responsive.js';

let table = new DataTable('#lab-notebook', {
    responsive: true
});

$(document).ready( function () {
    $('#lab-notebook').DataTable();
} );
