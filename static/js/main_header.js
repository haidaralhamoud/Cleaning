document.addEventListener("DOMContentLoaded", () => {
  const toggleBtn = document.getElementById("menu-toggle");
  const navLinks = document.getElementById("nav-links");
  const cartCount = document.getElementById("cartCount");

  if (toggleBtn && navLinks) {
    toggleBtn.addEventListener("click", () => {
      navLinks.classList.toggle("active");
    });
  }

  if (cartCount) {
    const url = cartCount.dataset.url;
    if (url) {
      fetch(url)
        .then((res) => res.json())
        .then((data) => {
          cartCount.textContent = data.count  0;
        })
        .catch(() => {});
    }
  }

  initCustomSelects();
});

const initCustomSelects = () => {
  const selects = Array.from(document.querySelectorAll("select")).filter((select) => {
    if (select.closest(".custom-select")) return false;
    if (select.hasAttribute("data-no-custom")) return false;
    if (select.multiple) return false;
    if (select.size && select.size > 1) return false;
    return true;
  });

  if (!selects.length) return;

  selects.forEach((select) => {
    const wrapper = document.createElement("div");
    wrapper.className = "custom-select";

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "custom-select-toggle";
    toggle.setAttribute("aria-haspopup", "listbox");
    toggle.setAttribute("aria-expanded", "false");
    toggle.innerHTML = `
      <span class="custom-select-label">Select...</span>
      <span class="custom-select-arrow" aria-hidden="true"></span>
    `;

    const menu = document.createElement("div");
    menu.className = "custom-select-menu";
    menu.setAttribute("role", "listbox");

    select.parentNode.insertBefore(wrapper, select);
    wrapper.appendChild(select);
    wrapper.appendChild(toggle);
    wrapper.appendChild(menu);

    const label = toggle.querySelector(".custom-select-label");

    const rebuildMenu = () => {
      menu.innerHTML = "";
      const selectedValue = select.value;

      Array.from(select.children).forEach((child) => {
        if (child.tagName === "OPTGROUP") {
          const groupLabel = document.createElement("div");
          groupLabel.className = "custom-select-group";
          groupLabel.textContent = child.label;
          menu.appendChild(groupLabel);

          Array.from(child.children).forEach((option) => {
            menu.appendChild(buildOption(option, selectedValue));
          });
        } else if (child.tagName === "OPTION") {
          menu.appendChild(buildOption(child, selectedValue));
        }
      });

      const currentOption = select.options[select.selectedIndex];
      label.textContent = currentOption  currentOption.textContent.trim() : "Select...";
    };

    const buildOption = (option, selectedValue) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "custom-select-option";
      btn.textContent = option.textContent;
      btn.dataset.value = option.value;
      btn.disabled = option.disabled;
      btn.setAttribute("role", "option");
      if (option.value === selectedValue) {
        btn.setAttribute("aria-selected", "true");
        btn.classList.add("is-selected");
      }
      if (option.disabled) {
        btn.classList.add("is-disabled");
      }
      btn.addEventListener("click", () => {
        if (option.disabled) return;
        select.value = option.value;
        select.dispatchEvent(new Event("change", { bubbles: true }));
        closeMenu(wrapper, toggle);
        rebuildMenu();
      });
      return btn;
    };

    const closeMenu = (wrap, toggleBtn) => {
      wrap.classList.remove("open");
      toggleBtn.setAttribute("aria-expanded", "false");
    };

    toggle.addEventListener("click", (e) => {
      e.stopPropagation();
      const isOpen = wrapper.classList.toggle("open");
      toggle.setAttribute("aria-expanded", String(isOpen));
    });

    document.addEventListener("click", () => {
      closeMenu(wrapper, toggle);
    });

    select.addEventListener("change", rebuildMenu);

    rebuildMenu();
  });
};

window.initCustomSelects = initCustomSelects;
