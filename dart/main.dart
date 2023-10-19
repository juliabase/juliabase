library juliabase;

import "dart:html";
part "result.dart";

void main() {
  final editURLRegexp = RegExp(r"^/results/\d+/edit/$");
  // FixMe: We don’t need onLoad once
  // https://bugs.chromium.org/p/chromium/issues/detail?id=874749 is finally
  // fixed.
  window.onLoad.listen((_) {
    if (window.location.pathname == "/results/add/" || editURLRegexp.hasMatch(window.location.pathname!)){
      resultInitializeAttachments();
      querySelector("#add-attachment")!
          .addEventListener("pointerdown", (_) => resultAppendAttachment());
    }
  });
}
