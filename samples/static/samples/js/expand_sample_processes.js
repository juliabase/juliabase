/*
 * Processes on the sample data sheet.
 *
 * Every process is a <details> element whose body htmx loads once, see the
 * "process" block in samples/show_sample.html.  Expanding and collapsing a
 * single process needs no JavaScript; this file only provides the
 * "Expand All"/"Collapse All" button and an error message for bodies that
 * could not be loaded.
 */
(() => {
    "use strict";

    const PROCESS_SELECTOR = 'details[data-js="process"]';
    const TOGGLE_ALL_BUTTON_SELECTOR = '[data-js="toggle-all-processes"]';

    function getProcesses() {
        return Array.from(document.querySelectorAll(PROCESS_SELECTOR));
    }

    function updateToggleAllButtons() {
        const areAllProcessesOpen = getProcesses().every(process => process.open);
        document.querySelectorAll(TOGGLE_ALL_BUTTON_SELECTOR).forEach(button => {
            button.textContent = areAllProcessesOpen ? button.dataset.labelCollapse : button.dataset.labelExpand;
        });
    }

    function showLoadError(event) {
        const processBody = event.detail.target;
        if (!processBody || !processBody.closest(PROCESS_SELECTOR)) return;
        processBody.textContent = processBody.dataset.loadErrorText;
    }

    document.addEventListener("click", event => {
        if (!event.target.closest(TOGGLE_ALL_BUTTON_SELECTOR)) return;
        const processes = getProcesses();
        const shouldOpen = processes.some(process => !process.open);
        // Opening fires the "toggle" event, which makes htmx load the body.
        processes.forEach(process => { process.open = shouldOpen; });
    });

    // "toggle" does not bubble, so it is caught in the capture phase.
    document.addEventListener("toggle", event => {
        if (event.target.matches && event.target.matches(PROCESS_SELECTOR)) updateToggleAllButtons();
    }, true);

    document.addEventListener("htmx:responseError", showLoadError);
    document.addEventListener("htmx:sendError", showLoadError);

    // The script is deferred, so the data sheet has already been parsed.
    updateToggleAllButtons();
})();
