document.addEventListener("DOMContentLoaded", function() {
    var prefixSpan = document.getElementById("name_prefix");
    var prefixInput = document.getElementById("name_prefix_data");

    if (prefixSpan && prefixInput) {
        prefixSpan.addEventListener("input", function () {
            prefixInput.value = prefixSpan.innerHTML;
        });
        prefixInput.value = prefixSpan.innerHTML;
    }
});
