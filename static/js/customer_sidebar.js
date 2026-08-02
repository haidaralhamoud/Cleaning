document.addEventListener(
  "DOMContentLoaded",
  () => {
    const toggle = document.getElementById("menuToggle");
    const sidebar = document.querySelector(".customer-sidebar");
    if (!toggle || !sidebar) return;
    if (toggle.dataset.customerSidebarReady === "1") return;
    toggle.dataset.customerSidebarReady = "1";

    let overlay = document.querySelector(".customer-menu-overlay");
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.className = "overlay customer-menu-overlay";
      overlay.id = "menuOverlay";
      document.body.appendChild(overlay);
    }

    const arrow = toggle.querySelector(".arrow");

    const setOpen = (open) => {
      sidebar.classList.toggle("open", open);
      overlay.classList.toggle("show", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      document.body.classList.toggle("customer-sidebar-open", open);
      if (arrow) {
        arrow.innerHTML = open ? "&#8249;" : "&#8250;";
      }
    };

    toggle.addEventListener(
      "click",
      (event) => {
        event.stopImmediatePropagation();
        setOpen(!sidebar.classList.contains("open"));
      },
      true
    );

    overlay.addEventListener(
      "click",
      (event) => {
        event.stopImmediatePropagation();
        setOpen(false);
      },
      true
    );

    sidebar.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", () => setOpen(false));
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") setOpen(false);
    });
  },
  true
);


