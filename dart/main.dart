library juliabase;

import "dart:html";
part "result.dart";

void main() {
  // FixMe: We don’t need onLoad once
  // https://bugs.chromium.org/p/chromium/issues/detail?id=874749 is finally
  // fixed.
  window.onLoad.listen((_) {
    if (window.location.pathname == "/results/add/") {
      querySelector("#add-attachment")!
          .addEventListener("pointerdown", resultAddAttachment);
    }
  });
}
