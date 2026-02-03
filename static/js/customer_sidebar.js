document.addEventListener(
  "DOMContentLoaded",
  () => {
    const toggle = document.getElementById("menuToggle");
    const sidebar = document.querySelector(".sidebar");
    if (!toggle || !sidebar) return;

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
  },
  true
);
