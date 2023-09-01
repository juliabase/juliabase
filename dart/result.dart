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
  final newAttach = document.createElement("tbody");
  newAttach.setAttribute("id", "${index}_attachment");
  newAttach.setAttribute("style", "border: 2px solid");
  final row = document.createElement("tr");
  newAttach.append(row);
  final firstCol = document.createElement("td");
  firstCol.setAttribute("class", "field-label");
  firstCol.setAttribute("style", "padding: 2ex");
  final secondCol = document.createElement("td");
  secondCol.setAttribute("class", "field-input");
  secondCol.setAttribute("style", "padding: 2ex");
  row.append(firstCol);
  row.append(secondCol);
  final label = document.createElement("label");
  label.setAttribute("for", "${index}_id_image_file");
  label.text = "Image file:";
  firstCol.append(label);
  final input = document.createElement("input");
  input.setAttribute("type", "file");
  input.setAttribute("name", "${index}_image_file");
  input.setAttribute("id", "${index}_id_image_file");
  secondCol.append(input);
  attachments.append(newAttach);
}
