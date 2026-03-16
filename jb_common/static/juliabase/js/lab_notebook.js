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
                                setTimeout(function() {
                                    $msg.fadeOut(500, function() {
                                        $(this).remove();
                                    });
                                }, 3000);
                            }

                            // Update form dropdowns if dates are provided
                            if (response.begin_date) {
                                updateDateDropdowns('begin_date', response.begin_date);
                            }
                            if (response.end_date) {
                                updateDateDropdowns('end_date', response.end_date);
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
                        
                        var msg = "An error occurred during update.";
                        if (xhr.responseJSON && xhr.responseJSON.message) {
                            msg = xhr.responseJSON.message;
                        }
                        
                        $('<div class="report-error">' + msg + '</div>').insertBefore('.main');
                        console.error("AJAX Error: " + status + error);
                    }
                });
            }

            // Function to update Django SelectDateWidget dropdowns
            function updateDateDropdowns(baseName, dateString) {
                // dateString format is YYYY-MM-DD
                var parts = dateString.split('-');
                if (parts.length === 3) {
                    var year = parseInt(parts[0], 10);
                    var month = parseInt(parts[1], 10);
                    var day = parseInt(parts[2], 10);

                    // Update dropdowns. Django names them baseName_year, baseName_month, baseName_day
                    $('select[name="' + baseName + '_year"]').val(year);
                    $('select[name="' + baseName + '_month"]').val(month);
                    $('select[name="' + baseName + '_day"]').val(day);
                }
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