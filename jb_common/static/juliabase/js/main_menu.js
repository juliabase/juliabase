function toggleSamples(id) {
    var samplesDiv = document.getElementById(id);
    if (samplesDiv.style.display === "none") {
      samplesDiv.style.display = "block";
    } else {
      samplesDiv.style.display = "none";
    }
  }