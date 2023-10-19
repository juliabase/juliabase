part of juliabase;

void resultAddAttachment() {
  final attachments = querySelector("#attachments")!;
  var index = -1;
  for (var c in attachments.children) {
    final i = int.parse(c.getAttribute("id")!.substring(3).split("-")[0]);
    if (i > index) {
      index = i;
    }
  }
  index++;

  final tbody = document.createElement("tbody");
  tbody.id = "id_${index}-attachment";

  final tr = document.createElement("tr");

  Element td, content;

  td = document.createElement("td");
  td.className = "field-label";
  td.setAttribute("style", "padding: 2ex; " +
    "border-left: 2px solid; border-top: 2px solid; border-bottom: 2px solid");

  content = document.createElement("label");
  content.setAttribute("for", "id_${index}-image_file");
  content.text = "Image file:";

  td.append(content);
  tr.append(td);

  td = document.createElement("td");
  td.className = "field-input";
  td.setAttribute("style", "padding: 2ex; border-top: 2px solid; border-bottom: 2px solid");

  content = document.createElement("input");
  content.setAttribute("type", "file");
  content.setAttribute("name", "${index}-image_file");
  content.id = "id_${index}-image_file";

  td.append(content);
  tr.append(td);

  td = document.createElement("td");
  td.className = "field-label";
  td.setAttribute("style", "padding: 2ex; border-top: 2px solid; border-bottom: 2px solid");

  content = document.createElement("label");
  content.setAttribute("for", "id_${index}-description");
  content.text = "Description:";

  td.append(content);
  tr.append(td);

  td = document.createElement("td");
  td.className = "field-input";
  td.setAttribute("style", "padding: 2ex; border-top: 2px solid; border-bottom: 2px solid; border-right: 2px solid");

  content = document.createElement("input");
  content.setAttribute("type", "text");
  content.setAttribute("required", "required");
  content.setAttribute("name", "${index}-description");
  content.id = "id_${index}-description";

  td.append(content);
  tr.append(td);

  td = document.createElement("td");

  content = document.createElement("span");
  content.setAttribute("style", "font-size: large; margin-left: 1em");
  content.text = "🗑";
  content.addEventListener("pointerdown", (_) => resultDeleteAttachment(index));

  td.append(content);
  tr.append(td);

  tbody.append(tr);

  attachments.append(tbody);
}

void resultDeleteAttachment(int index) {
  print(index);
}
