(function() {
  function loadScript(src, callback) {
    var script = document.createElement('script');
    script.src = src;
    script.onload = callback;
    document.head.appendChild(script);
  }
  
  function waitForJQuery(callback) {
    if (typeof jQuery !== 'undefined') {
      callback();
    } else {
      setTimeout(function() { waitForJQuery(callback); }, 50);
    }
  }
  
  waitForJQuery(function() {
    // Load DataTables after jQuery is ready
    loadScript('https://cdn.datatables.net/v/dt/dt-2.0.3/fc-5.0.0/fh-4.0.1/r-3.0.0/rg-1.5.0/datatables.min.js', function() {
      // Dispatch event so other scripts know DataTables is ready
      window.dispatchEvent(new Event('datatables-ready'));
    });
  });
})();
