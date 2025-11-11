  document.addEventListener("DOMContentLoaded", () => {
  const expandAllBtn = document.getElementById('expand_all');
  // var loadedAll = false;
  // let expandMode = true;

  async function loadProcess(id) {
    const body = document.getElementById(`process-body-${id}`);
    if (body.dataset.loaded === "true") return; // already loaded

    const loading = body.querySelector(".loading");
    loading.style.display = "block";

    try {
      const res = await fetch(`/process/${id}/${MISC.sample_id}/details/`);
      const data = await res.json();
      loading.style.display = "none";

      // Build HTML (factor into its own helper if you like)
        // Build HTML dynamically
        const html = [];
        document.getElementById(`process-title-${ id }`).style.display = "none";
        // Title
        html.push(`<h2 style="float:left" class="new-process-title" data-id="${id}">${data.name}</h2>`);
        // html.push(`<div class="new-content">`)

        if (MISC[`sample_clearance`]){
          var operator = data[`operator_safe`];
        }
        else {
          var operator = data[`operator_full_name`];
        }
        html.push(`<p class="operator_and_timestamp" style="margin-top: 3.6ex">${operator}, ${data["timestamp_display"]}</p>`);

        // Icons
        ["edit","delete","duplicate","export","resplit","zoom"].forEach(key => {
          const url = data[`${key}_url`];
          if(url){
            html.push(`
              <a class="edit-icon" href="${url}">
                <img src="${ICONS[key]}" alt="${key}" title="${TRANSLATIONS[key]}" width="16" height="16"/>
              </a>
            `);
          }
        });

        // Not finished
        if(!data.process.finished){
          html.push(`<span style="margin-left:2em;color:red;font-size:small">${TRANSLATIONS.not_finished}</span>`);
        }

        // Operator + timestamp
        html.push(`<div style="clear:both"></div>`);

        // Body
        html.push(`<div class="new-content">${data.html_body}</div>`);
        if(data.short_html_body){
          html.push(`<div class="new-short-content" style="display:none">${data.short_html_body}</div>`);
        }

        html.push(`<div style="clear:both"></div>`);

      body.innerHTML = html.join("");
      body.dataset.loaded = "true";
      body.dataset.visible = "true";
      body.style.display = "block";
      body.classList.remove("hidden");
    } catch (err) {
      loading.textContent = "Error loading process";
      console.error(err);
    }

    // // At this point, the body is either freshly loaded or was already loaded.
    // // Ensure it’s visible (expand if folded).
    // if (body.dataset.visible !== "true") {
    //   const new_content = body.querySelector(".new-content");
    //   const new_short_content = body.querySelector(".new-short-content");
    //   if (new_content) new_content.style.display = "block";
    //   if (new_short_content) new_short_content.style.display = "block";
    //   body.dataset.visible = "true";
    // }

}

async function runWithConcurrency(items, worker, limit = 3) {
  const queue = [...items];
  const running = [];

  async function runNext() {
    if (queue.length === 0) return;
    const item = queue.shift();
    const promise = worker(item).finally(() => {
      running.splice(running.indexOf(promise), 1);
    });
    running.push(promise);
    promise.then(runNext); // trigger next after finishing
  }

  // start `limit` initial workers
  for (let i = 0; i < limit && i < queue.length; i++) {
    runNext();
  }

  // wait until all done
  await Promise.all(running);
}

function checkVisible() {
  const headings = Array.from(document.querySelectorAll(".process-heading"));
  const ids = headings.map(h => h.closest(".process").dataset.id);

  let allExpanded = ids.every(id => {
    const body = document.getElementById(`process-body-${id}`);
    return body.dataset.visible === "true";
  });
  
  return allExpanded;
}

expandAllBtn.addEventListener("click", async () => {
  const headings = Array.from(document.querySelectorAll(".process-heading"));
  const ids = headings.map(h => h.closest(".process").dataset.id);

  await runWithConcurrency(ids, loadProcess, 3); // max 3 at a time

  // var all_true = true;
  // var all_expanded = true;
  // ids.forEach((id, index) => {
  //     const body = document.getElementById(`process-body-${id}`);
  //     all_true = all_true && body.dataset.loaded;
  //     all_expanded = all_expanded && body.dataset.visible;
  // });
  // // FIXME: You stopped aquí and it is not working properly
  // if (loadedAll === true){
  //   ids.forEach((id, index) => {
  //     const body = document.getElementById(`process-body-${id}`);

  //     const new_content = body.querySelector(".new-content");
  //     const new_short_content = body.querySelector(".new-short-content");

  //     if (all_expanded){
  //       // Already loaded → just toggle visibility
  //       if (body.dataset.visible === "true") {
  //         // body.classList.toggle("hidden");
  //         if (new_content) new_content.style.display = "none";
  //         if (new_short_content) new_short_content.style.display = "none";
  //         body.dataset.visible = "false";
  //         // return;
  //       }
  //     }
  //     else{
  //       if (new_content) new_content.style.display = "block";
  //       if (new_short_content) new_short_content.style.display = "block";
  //       body.dataset.visible = "true";
  //       // return;
  //     }

  //   });
  // }

  // if (all_true) {
  //   loadedAll = true;
  // }

  // ids.forEach(id => {
  //   const body = document.getElementById(`process-body-${id}`);
  //   const new_content = body.querySelector(".new-content");
  //   const new_short_content = body.querySelector(".new-short-content");

  //   if (expandMode) {
  //     // Expand everything
  //     if (new_content) new_content.style.display = "block";
  //     if (new_short_content) new_short_content.style.display = "block";
  //     body.dataset.visible = "true";
  //   } else {
  //     // Collapse everything
  //     if (new_content) new_content.style.display = "none";
  //     if (new_short_content) new_short_content.style.display = "none";
  //     body.dataset.visible = "false";
  //   }
  // });

  //   // Flip mode for next click
  //   expandMode = !expandMode;

  
  // Check if all are already expanded
  let allExpanded = checkVisible();
  // ids.every(id => {
  //   const body = document.getElementById(`process-body-${id}`);
  //   return body.dataset.visible === "true";
  // });

  ids.forEach(id => {
    const body = document.getElementById(`process-body-${id}`);
    const new_content = body.querySelector(".new-content");
    const new_short_content = body.querySelector(".new-short-content");

    if (allExpanded) {
      // Collapse all
      if (new_content) new_content.style.display = "none";
      if (new_short_content) new_short_content.style.display = "none";
      body.dataset.visible = "false";
      expandAllBtn.textContent = TRANSLATIONS["expand_all"];
    } else {
      // Expand all
      if (new_content) new_content.style.display = "block";
      if (new_short_content) new_short_content.style.display = "block";
      body.dataset.visible = "true";
      expandAllBtn.textContent = TRANSLATIONS["collapse_all"];
    }
  });

});

  document.querySelectorAll(".process-heading").forEach(heading => {
    heading.addEventListener("click", async () => {
      const id = heading.closest(".process").dataset.id;
      const body = document.getElementById(`process-body-${id}`);
      // const content = body.querySelector(".content");
      const loading = body.querySelector(".loading");

      // Already loaded → just toggle visibility
      if (body.dataset.loaded === "true") {
        body.classList.toggle("hidden");
        return;
      }
      loading.style.display = "block";
      // console.log(`/process/${id}/${MISC[`sample_id`]}/details/`);
      try {
        const res = await fetch(`/process/${id}/${MISC[`sample_id`]}/details/`);
        const data = await res.json();
        loading.style.display = "none";

        // Build HTML dynamically
        const html = [];
        document.getElementById(`process-title-${ id }`).style.display = "none";
        // Title
        html.push(`<h2 style="float:left" class="new-process-title" data-id="${id}">${data.name}</h2>`);
        // html.push(`<div class="new-content">`)

        if (MISC[`sample_clearance`]){
          var operator = data[`operator_safe`];
        }
        else {
          var operator = data[`operator_full_name`];
        }
        html.push(`<p class="operator_and_timestamp" style="margin-top: 3.6ex">${operator}, ${data["timestamp_display"]}</p>`);

        // Icons
        ["edit","delete","duplicate","export","resplit","zoom"].forEach(key => {
          const url = data[`${key}_url`];
          if(url){
            html.push(`
              <a class="edit-icon" href="${url}">
                <img src="${ICONS[key]}" alt="${key}" title="${TRANSLATIONS[key]}" width="16" height="16"/>
              </a>
            `);
          }
        });

        // Not finished
        if(!data.process.finished){
          html.push(`<span style="margin-left:2em;color:red;font-size:small">${TRANSLATIONS.not_finished}</span>`);
        }

        // Operator + timestamp
        html.push(`<div style="clear:both"></div>`);

        // Body
        html.push(`<div class="new-content">${data.html_body}</div>`);
        if(data.short_html_body){
          html.push(`<div class="new-short-content" style="display:none">${data.short_html_body}</div>`);
        }

        html.push(`<div style="clear:both"></div>`);

        body.innerHTML = html.join("");
        body.dataset.loaded = "true";
        body.dataset.visible = "true";
        body.style.display = "block";

      } catch(err){
        loading.textContent = "Error loading process";
        console.error(err);
      }
    });
  });

  document.addEventListener("click", e => {
  if (e.target.classList.contains("new-process-title")) {
    const id = e.target.dataset.id;
    const body = document.getElementById(`process-body-${id}`);

    const new_content = body.querySelector(".new-content");
    const new_short_content = body.querySelector(".new-short-content");

    // Already loaded → just toggle visibility
    if (body.dataset.visible === "true") {
      // body.classList.toggle("hidden");
      if (new_content) new_content.style.display = "none";
      if (new_short_content) new_short_content.style.display = "none";
      body.dataset.visible = "false";
      // expandAllBtn.textContent = TRANSLATIONS["expand_all"];

      let allExpanded = checkVisible();
      

      if(allExpanded)       expandAllBtn.textContent = TRANSLATIONS["collapse_all"];
      else       expandAllBtn.textContent = TRANSLATIONS["expand_all"];

      return;
    }
    else{
      if (new_content) new_content.style.display = "block";
      if (new_short_content) new_short_content.style.display = "block";
      body.dataset.visible = "true";

      let allExpanded = checkVisible();

      if(allExpanded)       expandAllBtn.textContent = TRANSLATIONS["collapse_all"];
      else       expandAllBtn.textContent = TRANSLATIONS["expand_all"];

      return;
    }
    
  }
});

});