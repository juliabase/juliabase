// This "script" is supposed to render Markdown and LaTex.
// It is weirdly written since we first convert the "Comments" column
// to MarkDown, and then we decide to load MathJax.
// Loading Marked and MathJax at the same time does not work properly
// since we always end up with the scenario that either MD or LaTeX 
// gets rendered. It also causes sometimes "race conditions" where
// MathJax ends up being called before it is loaded.
(function() {
    function processMarkdown() {
        if (typeof marked === 'undefined' || typeof DOMPurify === 'undefined') {
             return;
        }

        marked.setOptions({
            tables: true,
            gfm: true,
            breaks: true
        });

        // Define the data attributes of the columns you want to target
        const targetDataAttributes = ['comments', 'consequence', 'aim', 'execution', 'analysis_steps', 'software_and_version', 'result'];

        // Find the indices of the columns with the desired data attributes
        const columnIndices = targetDataAttributes.map(dataAttr => {
            return Array.from(document.querySelectorAll('th.top')).findIndex(th => th.getAttribute('data-column') === dataAttr) + 1;
        });

        // Function to preprocess text and fix missing newlines in markdown tables
        function preprocessMarkdownTables(text) {
            if (!text || !text.includes('|')) {
                return text;
            }
            
            // Pattern: `| |` (pipe-space-pipe) often indicates row boundary when newlines are missing
            // Replace `| |` with `|\n|` to restore table row breaks
            let processed = text.replace(/\| \|/g, '|\n|');
            
            // Also handle cases where there might be multiple spaces: `|  |`
            processed = processed.replace(/\|  \|/g, '|\n|');
            
            return processed;
        }

        // Function to convert text to Markdown
        function convertToMarkdown(cell) {
            if (cell.classList.contains('md-processed')) {
                return;
            }

            let originalText = cell.textContent;
            
            // Preprocess to fix missing newlines in tables
            originalText = preprocessMarkdownTables(originalText);
            
            // This beautiful if statement ignores any mathematical formula, because if we
            // interpret it as MD, well, the square brackets will be removed from the formula :)
            if (!originalText.startsWith('$') || !originalText.endsWith('$')) {
                // Sanitize the MD just in case someone does something sus with it
                try {
                    const sanitizedText = DOMPurify.sanitize(originalText);
                    const markdownText = marked(sanitizedText); // Use a Markdown library
                    cell.innerHTML = markdownText;

                    // Force re-rendering of all tables inside the cell
                    const tables = cell.querySelectorAll('table'); // Select all tables, not just the first one
                    tables.forEach(table => {
                        table.classList.add('markdown-table', 'table', 'table-bordered'); // Add class to each table
                    });
                } catch (e) {
                    console.error("md_latex_renderer: Error converting markdown", e);
                }
            }
            cell.classList.add('md-processed');
        }

        // Apply the Markdown conversion to each specified column
        columnIndices.forEach(columnIndex => {
            if (columnIndex > 0) { // Ensure the column index is valid
                const cells = document.querySelectorAll(`tr td:nth-child(${columnIndex})`);
                cells.forEach(cell => {
                    convertToMarkdown(cell);
                });
            }
        });

        // Now, apply Markdown conversion to <p> elements with the same data attributes
        targetDataAttributes.forEach(dataAttr => {
            const paragraphs = document.querySelectorAll(`p[data-column="${dataAttr}"]`);
            paragraphs.forEach(p => {
                convertToMarkdown(p);
            });
        });

        if (window.jQuery && window.jQuery.fn.dataTable) {
            var tables = window.jQuery.fn.dataTable.tables({ visible: true, api: true });
            tables.rows().invalidate().columns.adjust().draw();
        }
    }

    function initMathJax() {
        // Add MathJax configuration to enable both inline and display math
        if (!window.MathJax) {
            window.MathJax = {
                tex: {
                  inlineMath: [['$', '$'], ['\\(', '\\)']], // Enable $ ... $ for inline math
                  displayMath: [['$$', '$$'], ['\\[', '\\]']] // $$ ... $$ for display math
                },
                svg: {
                  fontCache: 'global'
                },
                startup: {
                    pageReady: () => {
                        return MathJax.startup.defaultPageReady().then(() => {
                            if (window.jQuery && window.jQuery.fn.dataTable) {
                                window.jQuery.fn.dataTable.tables({ visible: true, api: true }).columns.adjust().draw();
                                window.dispatchEvent(new Event('resize'));
                            }
                        });
                    }
                }
            };
        }

        // Now we import MathJax and let it do its magic :)
        if (!document.getElementById('MathJax-script')) {
            var mathJaxScript = document.createElement('script');
            mathJaxScript.src = "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js";
            mathJaxScript.id = "MathJax-script";
            mathJaxScript.async = true;
            document.head.appendChild(mathJaxScript);
        }
    }

    function main() {
        // Check if libraries are already available (loaded via defer)
        if (typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined') {
            processMarkdown();
            initMathJax();
            return;
        }

        // If not available yet, wait for them using a more efficient approach
        // This handles the case where scripts are still loading
        let loadCheckCount = 0;
        const maxChecks = 20; // 2 seconds max wait
        
        function checkAndProcess() {
            if (typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined') {
                processMarkdown();
                initMathJax();
            } else if (loadCheckCount < maxChecks) {
                loadCheckCount++;
                requestAnimationFrame(checkAndProcess);
            } else {
                console.error("md_latex_renderer: Markdown libraries failed to load. Aborting rendering.");
            }
        }
        
        // Use requestAnimationFrame for more efficient checking
        requestAnimationFrame(checkAndProcess);
    }

    // Execute when DOM is ready - scripts with defer will have loaded by then
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', main);
    } else {
        main();
    }
})();