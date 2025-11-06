// This "script" is supposed to render Markdown and LaTex.
// It is weirdly written since we first convert the "Comments" column
// to MarkDown, and then we decide to load MathJax.
// Loading Marked and MathJax at the same time does not work properly
// since we always end up with the scenario that either MD or LaTeX 
// gets rendered. It also causes sometimes "race conditions" where
// MathJax ends up being called before it is loaded.
document.addEventListener('DOMContentLoaded', function () {
    // Define the data attributes of the columns you want to target
    const targetDataAttributes = ['comments', 'consequence', 'aim', 'execution', 'analysis_steps', 'software_and_version', 'result']; // Add your data attributes here

    // Find the indices of the columns with the desired data attributes
    const columnIndices = targetDataAttributes.map(dataAttr => {
        return Array.from(document.querySelectorAll('th.top')).findIndex(th => th.getAttribute('data-column') === dataAttr) + 1;
    });

    // Function to convert text to Markdown
    function convertToMarkdown(cell) {
        const originalText = cell.textContent;
        // This beautiful if statement ignores any mathematical formula, because if we
        // interpret it as MD, well, the square brackets will be removed from the formula :)
        if (!originalText.startsWith('$') || !originalText.endsWith('$')) {
            // Sanitize the MD just in case someone does something sus with it
            const sanitizedText = DOMPurify.sanitize(originalText);
            const markdownText = marked(sanitizedText); // Use a Markdown library
            cell.innerHTML = markdownText;
        }
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


    // Now we import MathJax and let it do its magic :)
    var polyfillScript = document.createElement('script');
    polyfillScript.src = "https://polyfill.io/v3/polyfill.min.js?features=es6";
    document.head.appendChild(polyfillScript);

    var mathJaxScript = document.createElement('script');
    mathJaxScript.src = "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js";
    mathJaxScript.id = "MathJax-script";
    mathJaxScript.async = true;
    document.head.appendChild(mathJaxScript);
});