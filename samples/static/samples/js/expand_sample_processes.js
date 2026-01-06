  document.addEventListener("DOMContentLoaded", () => {
  const expandAllBtn = document.getElementById('expand_all');
    
  async function loadProcess(id) {
    const body = document.getElementById(`process-body-${id}`);
    if (body.dataset.loaded === "true") return; // already loaded

    const loading = body.querySelector(".loading");
    loading.style.display = "block";

    try {
      const res = await fetch(`/process/${id}/${MISC.sample_id}/details/`);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
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
        ["edit","delete","duplicate","export","resplit","show_process"].forEach(key => {
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

        // Force a valid root for malformed table fragments
        let safeHtml = data.html_body.trim();

        // If it starts with a table row or cell, wrap it in a table
        if (/^<(tr|td|tbody|thead|tfoot)[\s>]/i.test(safeHtml)) {
          safeHtml = `<table><tbody>${safeHtml}</tbody></table>`;
        }

        const html_body = $('<div>').html(safeHtml);

        // 1️⃣ Extract and execute <script> tags
        html_body.find('script').each(function() {
            // If it's an external script
            if (this.src) {
                const script = document.createElement('script');
                script.src = this.src;
                document.head.appendChild(script);
            } 
            // If it's inline JS
            else {
                $.globalEval(this.text || this.textContent || this.innerHTML || '');
            }
        });

        // Body
        html.push(`<div class="new-content">${html_body.html()}</div>`);
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
      console.error(`Process ${id} failed to load:`, err);
      throw err; // let runWithConcurrency handle retry
    }
}

async function runWithConcurrency(items, worker, limit = 3, maxRetries = 2, retryDelay = 1000) {
  const queue = items.map(item => ({ item, attempts: 0 }));
  const running = new Set();

  async function runNext() {
    if (queue.length === 0) return;

    const { item, attempts } = queue.shift();

    const promise = (async () => {
      try {
        await worker(item);
      } catch (err) {
        if (attempts < maxRetries) {
          console.warn(`Retrying ${item}, attempt ${attempts + 1}`);
          await new Promise(r => setTimeout(r, retryDelay)); // delay before retry
          queue.push({ item, attempts: attempts + 1 });
        } else {
          console.error(`Item ${item} failed after ${maxRetries + 1} tries`, err);
        }
      }
    })()
      .finally(() => {
        running.delete(promise);
        runNext(); // keep pipeline going
      });

    running.add(promise);
  }

  // start `limit` initial workers
  for (let i = 0; i < limit && i < queue.length; i++) {
    runNext();
  }

  // wait until both queue and running set are empty
  while (queue.length > 0 || running.size > 0) {
    await Promise.race(running); // wait for any to finish
  }
}

async function load_unfolded_processes() {
  const headings_init = Array.from(document.querySelectorAll(".process-heading"));
  const ids_init = headings_init.map(h => h.closest(".process").dataset.id);

  const res = await fetch(`/folded_processes_from_sample/${MISC['sample_id']}`);
  const data = await res.json();

  const title_ids = [];

  ids_init.forEach(processId => {
    const el = document.getElementById(`process-title-${processId}`);
    const title = el.firstChild.textContent.trim().toLowerCase();
    if (!data.includes(title)) title_ids.push(processId);
  });

  runWithConcurrency(title_ids, loadProcess, 3);
}

load_unfolded_processes();

function checkVisible() {
  const headings = Array.from(document.querySelectorAll(".process-heading"));
  const ids = headings.map(h => h.closest(".process").dataset.id);

  let allExpanded = ids.every(id => {
    const body = document.getElementById(`process-body-${id}`);
    return body.dataset.visible === "true";
  });
  return allExpanded;
}

// expandAllBtn.addEventListener("click", async () => {
//   const headings = Array.from(document.querySelectorAll(".process-heading"));
//   const ids = headings.map(h => h.closest(".process").dataset.id);

//   // First load only the not-yet-loaded processes
//   const unloaded = ids.filter(id => {
//     const body = document.getElementById(`process-body-${id}`);
//     return body.dataset.loaded !== "true";
//   });

//   if (unloaded.length > 0) {
//     await runWithConcurrency(unloaded, loadProcess, 3); // only load missing ones
//   }

//   // Now decide expand vs collapse
//   const allExpanded = checkVisible();

//   ids.forEach(id => {
//     const body = document.getElementById(`process-body-${id}`);
//     const new_content = body.querySelector(".new-content");
//     const new_short_content = body.querySelector(".new-short-content");

//     if (allExpanded) {
//       // Collapse all
//       if (new_content) new_content.style.display = "none";
//       if (new_short_content) new_short_content.style.display = "none";
//       body.dataset.visible = "false";
//     } else {
//       // Expand all
//       if (new_content) new_content.style.display = "block";
//       if (new_short_content) new_short_content.style.display = "block";
//       body.dataset.visible = "true";
//     }
//   });

//   // Update button label after
//   expandAllBtn.textContent = allExpanded
//     ? TRANSLATIONS["expand_all"]
//     : TRANSLATIONS["collapse_all"];
// });
expandAllBtn.addEventListener("click", async () => {
  const headings = Array.from(document.querySelectorAll(".process-heading"));
  const ids = headings.map(h => h.closest(".process").dataset.id);

  // Decide what we want to do before any loads mutate dataset.visible
  // If any process is currently collapsed -> we want to EXPAND all
  const shouldExpand = ids.some(id => {
    const body = document.getElementById(`process-body-${id}`);
    return body.dataset.visible !== "true";
  });

  // Load only the not-yet-loaded processes (await them)
  const unloaded = ids.filter(id => {
    const body = document.getElementById(`process-body-${id}`);
    return body.dataset.loaded !== "true";
  });
  if (unloaded.length > 0) {
    await runWithConcurrency(unloaded, loadProcess, 3);
  }

  // Now apply the pre-decided action to every process
  ids.forEach(id => {
    const body = document.getElementById(`process-body-${id}`);
    const new_content = body.querySelector(".new-content");
    const new_short_content = body.querySelector(".new-short-content");

    if (shouldExpand) {
      // Expand all
      if (new_content) new_content.style.display = "block";
      if (new_short_content) new_short_content.style.display = "block";
      body.dataset.visible = "true";
    } else {
      // Collapse all
      if (new_content) new_content.style.display = "none";
      if (new_short_content) new_short_content.style.display = "none";
      body.dataset.visible = "false";
    }
  });

  // Update button label accordingly
  expandAllBtn.textContent = shouldExpand ? TRANSLATIONS["collapse_all"] : TRANSLATIONS["expand_all"];
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
      if (new_content) new_content.style.display = "none";
      if (new_short_content) new_short_content.style.display = "none";
      body.dataset.visible = "false";

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