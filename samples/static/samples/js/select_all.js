function toggleSelectAll() {
    // Get the state of the "Select All" checkbox
    const selectAllCheckbox = document.getElementById('select_all');
    const isChecked = selectAllCheckbox.checked;

    // Find all checkboxes with the class "sample-checkbox"
    const checkboxes = document.querySelectorAll('.sample-checkbox');

    // Set each sample checkbox to the same checked state
    checkboxes.forEach(checkbox => {
        checkbox.checked = isChecked;
    });
}