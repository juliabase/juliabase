// Select / deselect all checkboxes on button click
function toggleCheckboxes() {
    var checkboxes = document.querySelectorAll('input[type="checkbox"]');
    allChecked = are_checkboxes_checked();
    for (var i = 0; i < checkboxes.length; i++) {
        checkboxes[i].checked = !allChecked;
    }
    refresh_select_button_text();
}

// Change the button caption on checkbox check if any box is checked or all unchecked
function refresh_select_button_text() {
    allChecked = are_checkboxes_checked();
    var button = document.getElementById('toggleButton');
    button.textContent = !allChecked ? 'Select all' : 'Deselect all';
}

// check if any checkbox on the page is checked
function are_checkboxes_checked() {
    var checkboxes = document.querySelectorAll('input[type="checkbox"]');
    var allChecked = Array.from(checkboxes).some(x => x.checked);
    return allChecked;
}

// Add a Event-Listener for each Checkbox
document.addEventListener('DOMContentLoaded', function() {
    var checkboxes = document.querySelectorAll('input[type="checkbox"]');
    for (var i = 0; i < checkboxes.length; i++) {
        checkboxes[i].addEventListener('change', refresh_select_button_text);
    }
    refresh_select_button_text();
});