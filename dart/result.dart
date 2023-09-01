part of juliabase;

void resultAddAttachment() {
  final attachments = querySelector("#attachments")!;
  var index = 0;
  for (var c in attachments.children) {
    final i = int.parse(c.getAttribute("id")!.split("_")[0]);
    if (i > index) {
      index = i;
    }
  }
  index++;

  final tbody = document.createElement("tbody");
  tbody.setAttribute("id", "${index}_attachment");
  tbody.setAttribute("style", "border: 2px solid");

  final tr = document.createElement("tr");

  Element td, content;

  td = document.createElement("td");
  td.setAttribute("class", "field-label");
  td.setAttribute("style", "padding: 2ex");

  content = document.createElement("label");
  content.setAttribute("for", "${index}_id_image_file");
  content.text = "Image file:";

  td.append(content);
  tr.append(td);

  td = document.createElement("td");
  td.setAttribute("class", "field-input");
  td.setAttribute("style", "padding: 2ex");

  content = document.createElement("input");
  content.setAttribute("type", "file");
  content.setAttribute("name", "${index}_image_file");
  content.setAttribute("id", "${index}_id_image_file");

  td.append(content);
  tr.append(td);

  td = document.createElement("td");
  td.setAttribute("class", "field-label");
  td.setAttribute("style", "padding: 2ex");

  content = document.createElement("label");
  content.setAttribute("for", "${index}_id_description");
  content.text = "Description:";

  td.append(content);
  tr.append(td);

  td = document.createElement("td");
  td.setAttribute("class", "field-input");
  td.setAttribute("style", "padding: 2ex");

  content = document.createElement("input");
  content.setAttribute("type", "text");
  content.setAttribute("name", "${index}_description");
  content.setAttribute("id", "${index}_id_description");

  td.append(content);
  tr.append(td);

  tbody.append(tr);

  attachments.append(tbody);
}
