  document.addEventListener("DOMContentLoaded", () => {
  const expandAllBtn = document.getElementById('expand_all');
    
  expandAllBtn.addEventListener('click', async () => {
    document.querySelectorAll(".process-heading").forEach(async heading => {
      const id = heading.closest(".process").dataset.id;
      const body = document.getElementById(`process-body-${id}`);
      const loading = body.querySelector(".loading");

      // If not yet loaded, fetch content (basically same as your click handler)
      if (body.dataset.loaded !== "true") {
        loading.style.display = "block";

        // fetch your details here (whatever you’re already doing in the single click handler)
try {
        const res = await fetch(`/process/${id}/details/`);
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
      }catch(err){
        loading.textContent = "Error loading process";
        console.error(err);
      }
      }

      // Ensure it’s visible
      body.classList.remove("hidden");
    });
  });

  document.querySelectorAll(".process-heading").forEach(heading => {
    heading.addEventListener("click", async () => {
      const id = heading.closest(".process").dataset.id;
      const body = document.getElementById(`process-body-${id}`);
      const loading = body.querySelector(".loading");

      // Already loaded → just toggle visibility
      if (body.dataset.loaded === "true") {
        body.classList.toggle("hidden");
        return;
      }
      
      loading.style.display = "block";

      try {
        const res = await fetch(`/process/${id}/details/`);
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

      } catch(err){
        loading.textContent = "Error loading process";
        console.error(err);
      }
    });
  });
});