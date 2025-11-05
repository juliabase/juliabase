// This "script" is supposed to render Markdown and LaTex.
// It is weirdly written since we first convert the "Comments" column
// to MarkDown, and then we decide to load MathJax.
// Loading Marked and MathJax at the same time does not work properly
// since we always end up with the scenario that either MD or LaTeX 
// gets rendered. It also causes sometimes "race conditions" where
// MathJax ends up being called before it is loaded.
document.addEventListener('DOMContentLoaded', function () {
// Find the index of the column with the desired header content
const columnIndex = Array.from(document.querySelectorAll('th.top')).findIndex(th => th.textContent.trim() === 'Comments') + 1;
// Find all elements in the "Comments" column
const commentCells = document.querySelectorAll(`tr td:nth-child(${columnIndex})`);

// Convert each comment to Markdown
commentCells.forEach(cell => {
    const originalText = cell.textContent;
    // This beautiful if statement ignores any mathematical formula, because if we
    // interpret it as MD, well, the square brackets will be removed from the formula :)
    if (!originalText.startsWith('$') || !originalText.endsWith('$')) {
        // Sanitize the MD just in case someone does something sus with it
        const sanitizedText = DOMPurify.sanitize(originalText);
        const markdownText = marked(sanitizedText); // Use a Markdown library
        cell.innerHTML = markdownText;
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