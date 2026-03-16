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
        // Inject CSS to fix DataTables vertical gap issues (specifically for Bootstrap + scrollY)
        // We do this via JS to ensure it applies even if CSS files are cached or not loaded in all contexts.
        // This covers DataTables 1.x and 2.x class names.
        var fixStyles = `
            .dataTables_scrollHead,
            .dataTables_scrollHeadInner,
            .dt-scroll-head,
            .dt-scroll-headInner {
                margin-bottom: 0 !important;
                padding-bottom: 0 !important;
            }
            .dataTables_scrollBody,
            .dt-scroll-body {
                margin-top: 0 !important;
                padding-top: 0 !important;
            }
            .dataTables_scrollHeadInner table,
            .dt-scroll-headInner table,
            .dataTables_scrollHead table,
            .dt-scroll-head table,
            .dataTables_wrapper table.dataTable,
            div.dt-container table.dataTable {
                margin-bottom: 0 !important;
                margin-top: 0 !important;
                border-collapse: collapse !important;
            }
            /* FixedColumns gap fix */
            .dtfc-fixed-left,
            .dtfc-fixed-right,
            .dt-fixedColumns-left,
            .dt-fixedColumns-right {
                margin-top: 0 !important;
            }
        `;
        var styleSheet = document.createElement("style");
        styleSheet.type = "text/css";
        styleSheet.innerText = fixStyles;
        document.head.appendChild(styleSheet);

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
            
            // Shared AJAX function for notebook updates
            function performNotebookUpdate(url, method, data) {
                // Show loading message
                $('.report-success, .report-error, .report-info, .report-warning').remove();
                var $loading = $('<div class="report-info">' + gettext('Updating lab notebook...') + '</div>').insertBefore('.main');
                $loading.css({
                    'position': 'fixed',
                    'top': '20px',
                    'left': '50%',
                    'transform': 'translateX(-50%)',
                    'z-index': '9999',
                    'box-shadow': '0 4px 6px rgba(0,0,0,0.1)',
                    'min-width': '300px',
                    'text-align': 'center'
                });

                $.ajax({
                    type: method,
                    url: url, 
                    data: data,
                    headers: {'X-Requested-With': 'XMLHttpRequest'},
                    success: function(response) {
                        // Clear existing messages
                        $('.report-success, .report-error, .report-info, .report-warning').remove();

                        if (response.html_body) {
                            // Show success message if present
                            if (response.message) {
                                var $msg = $('<div class="report-success">' + response.message + '</div>').insertBefore('.main');
                                $msg.css({
                                    'position': 'fixed',
                                    'top': '20px',
                                    'left': '50%',
                                    'transform': 'translateX(-50%)',
                                    'z-index': '9999',
                                    'box-shadow': '0 4px 6px rgba(0,0,0,0.1)',
                                    'min-width': '300px',
                                    'text-align': 'center'
                                });
                                setTimeout(function() {
                                    $msg.fadeOut(500, function() {
                                        $(this).remove();
                                    });
                                }, 3000);
                            }

                            // Update form inputs if dates are provided via response (which means update was successful)
                            if (response.begin_date) {
                                // Assume response format is YYYY-MM-DD (ISO)
                                // Flatpickr instance, if available, can parse ISO
                                var beginInput = document.getElementById('id_begin_date');
                                if (beginInput && beginInput._flatpickr) {
                                    beginInput._flatpickr.setDate(response.begin_date, true, 'Y-m-d');
                                } else {
                                    // Fallback if no flatpickr
                                    $('input[name="begin_date"]').val(response.begin_date);
                                }
                            }
                            if (response.end_date) {
                                var endInput = document.getElementById('id_end_date');
                                if (endInput && endInput._flatpickr) {
                                    endInput._flatpickr.setDate(response.end_date, true, 'Y-m-d');
                                } else {
                                    $('input[name="end_date"]').val(response.end_date);
                                }
                            }

                            // Destroy existing DataTables to prevent memory leaks or errors
                             $('.lab-notebook:not(.manual-datatable)').each(function() {
                                if ($.fn.DataTable.isDataTable(this)) {
                                    $(this).DataTable().destroy();
                                }
                            });

                            // update content
                            $('.lock-header').html(response.html_body);
                            
                            // update navigation buttons
                            if (response.previous_url) {
                                $('img[src$="book_previous.png"]').parent('a').attr('href', response.previous_url).css('visibility', 'visible');
                            } else {
                               $('img[src$="book_previous.png"]').parent('a').css('visibility', 'hidden');
                            }

                            if (response.next_url) {
                                $('img[src$="book_next.png"]').parent('a').attr('href', response.next_url).css('visibility', 'visible');
                            } else {
                                $('img[src$="book_next.png"]').parent('a').css('visibility', 'hidden');
                            }
                            
                            // Update export URL
                             if (response.export_url) {
                                $('a.edit-icon').attr('href', response.export_url).show();
                            } else {
                                $('a.edit-icon').hide();
                            }

                            // Update browser URL
                             if (response.new_url) {
                                window.history.pushState(null, response.title, response.new_url);
                                if (response.title) {
                                    document.title = response.title;
                                }
                            }
                            
                            // Re-initialize tables
                            initLabNotebook();
                        } else {
                             window.location.reload();
                        }
                    },
                    error: function(xhr, status, error) {
                        // Clear existing messages
                        $('.report-success, .report-error, .report-info, .report-warning').remove();
                        
                        var msg = gettext("An error occurred during update.");
                        if (xhr.responseJSON && xhr.responseJSON.message) {
                            msg = xhr.responseJSON.message;
                        }
                        
                        var $err = $('<div class="report-error">' + msg + '</div>').insertBefore('.main');
                        $err.css({
                            'position': 'fixed',
                            'top': '20px',
                            'left': '50%',
                            'transform': 'translateX(-50%)',
                            'z-index': '9999',
                            'box-shadow': '0 4px 6px rgba(0,0,0,0.1)',
                            'min-width': '300px',
                            'text-align': 'center'
                        });
                        setTimeout(function() {
                            $err.fadeOut(500, function() {
                                $(this).remove();
                            });
                        }, 5000); // 5 seconds duration for error messages
                        console.error("AJAX Error: " + status + error);
                    }
                });
            }

            // Quick date selection handler
            $('.quick-date').on('click', function() {
                var range = $(this).data('range');
                var today = new Date();
                var start = new Date(today); // Clone today
                var end = new Date(today);   // Clone today

                function formatDate(date) {
                     // Return date object for flatpickr or YYYY-MM-DD string
                     var year = date.getFullYear();
                     var month = (date.getMonth() + 1).toString().padStart(2, '0');
                     var day = date.getDate().toString().padStart(2, '0');
                     return year + '-' + month + '-' + day;
                }

                if (range === 'today') {
                    // start and end are today
                } else if (range === 'this-week') {
                    // Calculate start of week (Monday)
                    var day = today.getDay(); // 0 (Sun) to 6 (Sat)
                    var diff = day === 0 ? 6 : day - 1; // Days to subtract to get Monday
                    start.setDate(today.getDate() - diff);
                    
                    // Calculate end of week (Sunday)
                    var endOfWeek = new Date(start);
                    endOfWeek.setDate(start.getDate() + 6);
                    end = endOfWeek;
                } else if (range === 'this-month') {
                    // Start of month
                    start.setDate(1);
                    // End of month (0th day of next month gets last day of previous month)
                    end = new Date(today.getFullYear(), today.getMonth() + 1, 0);
                } else if (range === 'last-7') {
                    // 7 days ago (inclusive of today means today - 6 days)
                    start.setDate(today.getDate() - 6);
                } else if (range === 'last-30') {
                    // 30 days ago (inclusive of today means today - 29 days)
                    start.setDate(today.getDate() - 29);
                }

                // Update Pickers
                var beginInput = document.getElementById('id_begin_date');
                var endInput = document.getElementById('id_end_date');
                
                if (beginInput._flatpickr) {
                    beginInput._flatpickr.setDate(start);
                } else {
                     $(beginInput).val(formatDate(start));
                }
                if (endInput._flatpickr) {
                    endInput._flatpickr.setDate(end);
                } else {
                     $(endInput).val(formatDate(end));
                }
                
                // Trigger form submission
                $('#date-form').submit();
            });

            // Initialize Flatpickr
            if (typeof flatpickr !== 'undefined') {
                var lang = $('#date-form').data('lang') || 'en';
                flatpickr(".date-picker", {
                    dateFormat: "d.m.Y",
                    allowInput: true,
                    locale: lang
                });
            }

            // Add AJAX submit handler
            $('#date-form').on('submit', function(e) {
                e.preventDefault();
                performNotebookUpdate(window.location.href, 'POST', $(this).serialize());
            });

            // Add AJAX handler for previous/next buttons
            $(document).on('click', 'a', function(e) {
                var $target = $(this);
                // Check if this anchor contains our specific navigation images
                if ($target.find('img[src$="book_previous.png"]').length > 0 || $target.find('img[src$="book_next.png"]').length > 0) {
                     e.preventDefault();
                     var url = $target.attr('href');
                     if (url) {
                         performNotebookUpdate(url, 'GET', null);
                     }
                }
            });
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
    // Initialize each table individually so we can run post-init adjustments
    $('.lab-notebook:not(.manual-datatable)').each(function() {
        var $tbl = $(this);
        var table = $tbl.DataTable({
            order: [],
            // pageLength: 50,
            scrollX: true,
            scrollY: '50vh',
            scrollCollapse: true,
            autoWidth: false,
            language: langDict,
            fixedColumns: true,
            // fixedHeader: true // Disable FixedHeader as it conflicts with scrollY
        });

        // Some layout issues persist until DataTables has finished sizing.
        // Run a couple of adjustments after init and shortly after to force
        // the header/body alignment to recompute.
        function adjustLayout() {
            try { table.columns.adjust(); } catch (e) {}
            if (table.responsive) {
                try { table.responsive.recalc(); } catch (e) {}
            }
        }

        adjustLayout();

        // Use requestAnimationFrame for better timing with render cycle
        if (window.requestAnimationFrame) {
            requestAnimationFrame(function() {
                adjustLayout();
                setTimeout(adjustLayout, 200);
            });
        } else {
            setTimeout(adjustLayout, 200);
        }
    });
    
    if (typeof window.no_bs5 === 'undefined' || window.no_bs5 === false) {
        // Use jQuery to select the specific div and find its child table element
        var $table = $('.lock-header').find('table');
    
        if ($table.length) {
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
    }
    } // end initLabNotebook
    }); // end waitForJQuery callback
})();