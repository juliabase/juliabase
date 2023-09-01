library juliabase;

import "dart:html";

void main() {

  // FixMe: We don’t need onLoad once
  // https://bugs.chromium.org/p/chromium/issues/detail?id=874749 is finally
  // fixed.
  window.onLoad.listen((_) {
    print(window.location.href);
  });
}
