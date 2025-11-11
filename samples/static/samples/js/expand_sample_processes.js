  document.addEventListener("DOMContentLoaded", () => {
  const expandAllBtn = document.getElementById('expand_all');

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
      const html = [];
      document.getElementById(`process-title-${id}`).style.display = "none";
      html.push(`<h2 style="float:left">${data.name}</h2>`);
      const operator = MISC.sample_clearance ? data.operator_safe : data.operator_full_name;
      html.push(`<p class="operator_and_timestamp" style="margin-top: 3.6ex">${operator}, ${data.timestamp_display}</p>`);

      ["edit","delete","duplicate","export","resplit","zoom"].forEach(key => {
        const url = data[`${key}_url`];
        if (url) {
          html.push(`
            <a class="edit-icon" href="${url}">
              <img src="${ICONS[key]}" alt="${key}" title="${TRANSLATIONS[key]}" width="16" height="16"/>
            </a>
          `);
        }
      });

      if (!data.process.finished) {
        html.push(`<span style="margin-left:2em;color:red;font-size:small">${TRANSLATIONS.not_finished}</span>`);
      }

      html.push(`<div style="clear:both"></div>`);
      html.push(`<div>${data.html_body}</div>`);
      if (data.short_html_body) {
        html.push(`<div style="display:none">${data.short_html_body}</div>`);
      }
      html.push(`<div style="clear:both"></div>`);

      body.innerHTML = html.join("");
      body.dataset.loaded = "true";
      body.style.display = "block";
      body.classList.remove("hidden");
    } catch (err) {
      loading.textContent = "Error loading process";
      console.error(err);
    }
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

expandAllBtn.addEventListener("click", async () => {
  const headings = Array.from(document.querySelectorAll(".process-heading"));
  const ids = headings.map(h => h.closest(".process").dataset.id);

  await runWithConcurrency(ids, loadProcess, 3); // max 3 at a time
});


    
//   expandAllBtn.addEventListener('click', async () => {
//     document.querySelectorAll(".process-heading").forEach(async heading => {
//       const id = heading.closest(".process").dataset.id;
//       const body = document.getElementById(`process-body-${id}`);
//       const loading = body.querySelector(".loading");

//       // If not yet loaded, fetch content (basically same as your click handler)
//       if (body.dataset.loaded !== "true") {
//         loading.style.display = "block";

//         // fetch your details here (whatever you’re already doing in the single click handler)
// try {
//         const res = await fetch(`/process/${id}/${MISC[`sample_id`]}/details/`);
//         const data = await res.json();
//         loading.style.display = "none";

//         // Build HTML dynamically
//         const html = [];
//         document.getElementById(`process-title-${ id }`).style.display = "none";
//         // Title
//         html.push(`<h2 style="float:left">${data.name}</h2>`);

//         if (MISC[`sample_clearance`]){
//           var operator = data[`operator_safe`];
//         }
//         else {
//           var operator = data[`operator_full_name`];
//         }
//         html.push(`<p class="operator_and_timestamp" style="margin-top: 3.6ex">${operator}, ${data["timestamp_display"]}</p>`);

//         // Icons
//         ["edit","delete","duplicate","export","resplit","zoom"].forEach(key => {
//           const url = data[`${key}_url`];
//           if(url){
//             html.push(`
//               <a class="edit-icon" href="${url}">
//                 <img src="${ICONS[key]}" alt="${key}" title="${TRANSLATIONS[key]}" width="16" height="16"/>
//               </a>
//             `);
//           }
//         });

//         // Not finished
//         if(!data.process.finished){
//           html.push(`<span style="margin-left:2em;color:red;font-size:small">${TRANSLATIONS.not_finished}</span>`);
//         }

//         // Operator + timestamp
//         html.push(`<div style="clear:both"></div>`);

//         // Body
//         html.push(`<div>${data.html_body}</div>`);
//         if(data.short_html_body){
//           html.push(`<div style="display:none">${data.short_html_body}</div>`);
//         }

//         html.push(`<div style="clear:both"></div>`);

//         body.innerHTML = html.join("");
//         body.dataset.loaded = "true";
//         body.style.display = "block";
//       }catch(err){
//         loading.textContent = "Error loading process";
//         console.error(err);
//       }
//       }

//       // Ensure it’s visible
//       body.classList.remove("hidden");
//     });
//   });

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
        html.push(`<h2 style="float:left">${data.name}</h2>`);

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
        html.push(`<div>${data.html_body}</div>`);
        if(data.short_html_body){
          html.push(`<div style="display:none">${data.short_html_body}</div>`);
        }

        html.push(`<div style="clear:both"></div>`);

        body.innerHTML = html.join("");
        body.dataset.loaded = "true";
        body.style.display = "block";

      } catch(err){
        loading.textContent = "Error loading process";
        console.error(err);
      }
    });
  });
});