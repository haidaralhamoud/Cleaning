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
          cartCount.textContent = data.count || 0;
        })
        .catch(() => {});
    }
  }

  initCustomSelects();
  initFormValidation();
  initHemblaCalendar();
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
      label.textContent = currentOption ? currentOption.textContent.trim() : "Select...";
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

const ensureToastWrap = () => {
  let toastWrap = document.querySelector(".toast-wrap");
  if (!toastWrap) {
    toastWrap = document.createElement("div");
    toastWrap.className = "toast-wrap";
    document.body.appendChild(toastWrap);
  }
  return toastWrap;
};

const showToast = (title, desc) => {
  const toastWrap = ensureToastWrap();
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.innerHTML = `
    <div class="toast__title">${title}</div>
    <div class="toast__desc">${desc}</div>
  `;
  toastWrap.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add("show"));
  setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => toast.remove(), 200);
  }, 3000);
};

window.showToast = showToast;

const initFormValidation = () => {
  const forms = Array.from(document.querySelectorAll("form")).filter(
    (form) => !form.hasAttribute("data-skip-validate")
  );
  if (!forms.length) return;

  const markInvalid = (field) => {
    if (!field) return;
    if (field.closest(".custom-select")) {
      field.closest(".custom-select").classList.add("field-error-pill");
    } else {
      field.classList.add("field-error");
    }
  };

  const clearInvalid = (field) => {
    if (!field) return;
    if (field.closest(".custom-select")) {
      field.closest(".custom-select").classList.remove("field-error-pill");
    } else {
      field.classList.remove("field-error");
    }
  };

  forms.forEach((form) => {
    const isEmpty = (value) => !value || !String(value).trim();

    const collectInvalidFields = () => {
      const invalid = [];
      const radioGroups = new Map();
      const checkboxGroups = new Map();

      form.querySelectorAll("input, textarea, select").forEach((field) => {
        if (field.disabled) return;
        if (field.hasAttribute("data-optional")) return;
        if (field.type === "hidden") return;
        if (field.type === "submit" || field.type === "button") return;
        if (field.type === "file" && !field.required) return;

        if (field.type === "radio") {
          radioGroups.set(field.name, radioGroups.get(field.name) || []);
          radioGroups.get(field.name).push(field);
          return;
        }

        if (field.type === "checkbox") {
          checkboxGroups.set(field.name, checkboxGroups.get(field.name) || []);
          checkboxGroups.get(field.name).push(field);
          return;
        }

        if (field.tagName === "SELECT" && field.multiple) {
          if (!Array.from(field.selectedOptions).length) {
            invalid.push(field);
          }
          return;
        }

        if (field.tagName === "SELECT") {
          if (isEmpty(field.value)) invalid.push(field);
          return;
        }

        if (isEmpty(field.value)) invalid.push(field);
      });

      radioGroups.forEach((group) => {
        const anyChecked = group.some((field) => field.checked);
        if (!anyChecked) invalid.push(group[0]);
      });

      checkboxGroups.forEach((group) => {
        const anyChecked = group.some((field) => field.checked);
        if (!anyChecked) invalid.push(group[0]);
      });

      return invalid;
    };

    form.addEventListener("submit", (e) => {
      const invalidFields = collectInvalidFields();
      if (invalidFields.length) {
        e.preventDefault();
        invalidFields.forEach(markInvalid);
        showToast("Missing information", "Please complete the highlighted fields.");
      }
    });

    form.querySelectorAll("input, textarea, select").forEach((field) => {
      field.addEventListener("input", () => clearInvalid(field));
      field.addEventListener("change", () => clearInvalid(field));
    });
  });
};

const initHemblaCalendar = () => {
  const inputs = Array.from(document.querySelectorAll('input[type="date"]')).filter(
    (input) =>
      !input.hasAttribute("data-native-date") &&
      !input.hasAttribute("data-no-calendar") &&
      !input.classList.contains("hidden")
  );

  if (!inputs.length) return;

  const monthNames = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
  ];
  const weekdayNames = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];

  const wrap = document.createElement("div");
  wrap.className = "hembla-calendar";
  wrap.setAttribute("aria-hidden", "true");
  wrap.innerHTML = `
    <div class="hembla-calendar__header">
      <div class="hembla-calendar__title">HEMBLA BOOKING</div>
    </div>
    <div class="hembla-calendar__body">
      <button type="button" class="hembla-calendar__nav hembla-calendar__prev" aria-label="Previous month">&lsaquo;</button>
      <div class="hembla-calendar__month"></div>
      <button type="button" class="hembla-calendar__nav hembla-calendar__next" aria-label="Next month">&rsaquo;</button>
      <div class="hembla-calendar__weekdays"></div>
      <div class="hembla-calendar__days"></div>
    </div>
    <div class="hembla-calendar__footer">Powered by Hembla</div>
  `;

  const monthEl = wrap.querySelector(".hembla-calendar__month");
  const daysEl = wrap.querySelector(".hembla-calendar__days");
  const weekdaysEl = wrap.querySelector(".hembla-calendar__weekdays");
  const prevBtn = wrap.querySelector(".hembla-calendar__prev");
  const nextBtn = wrap.querySelector(".hembla-calendar__next");

  weekdayNames.forEach((day) => {
    const span = document.createElement("span");
    span.textContent = day;
    weekdaysEl.appendChild(span);
  });

  const state = {
    year: 0,
    month: 0,
    activeInput: null,
  };

  const pad = (value) => String(value).padStart(2, "0");

  const formatDate = (year, monthIndex, day) => {
    return `${year}-${pad(monthIndex + 1)}-${pad(day)}`;
  };

  const parseDate = (value) => {
    if (!value) return null;
    const parts = value.split("-");
    if (parts.length !== 3) return null;
    const year = Number(parts[0]);
    const month = Number(parts[1]) - 1;
    const day = Number(parts[2]);
    if (!year || month < 0 || day < 1) return null;
    return { year, month, day };
  };

  const render = () => {
    const year = state.year;
    const month = state.month;
    monthEl.textContent = `${monthNames[month]} ${year}`;

    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const selected = parseDate(state.activeInput ? state.activeInput.value : "");
    const today = new Date();
    const todayKey = formatDate(today.getFullYear(), today.getMonth(), today.getDate());

    daysEl.innerHTML = "";
    for (let i = 0; i < firstDay; i += 1) {
      const empty = document.createElement("span");
      empty.className = "hembla-calendar__empty";
      daysEl.appendChild(empty);
    }

    for (let day = 1; day <= daysInMonth; day += 1) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "hembla-calendar__day";
      btn.textContent = String(day);
      const key = formatDate(year, month, day);

      if (selected && selected.year === year && selected.month === month && selected.day === day) {
        btn.classList.add("is-selected");
      }
      if (key === todayKey) {
        btn.classList.add("is-today");
      }

      btn.addEventListener("click", () => {
        if (!state.activeInput) return;
        state.activeInput.value = key;
        state.activeInput.dispatchEvent(new Event("change", { bubbles: true }));
        closeCalendar();
      });
      daysEl.appendChild(btn);
    }
  };

  const positionCalendar = (input) => {
    const rect = input.getBoundingClientRect();
    const top = rect.bottom + window.scrollY + 10;
    let left = rect.left + window.scrollX;
    const calendarWidth = 320;
    if (left + calendarWidth > window.innerWidth) {
      left = window.innerWidth - calendarWidth - 20;
    }
    wrap.style.top = `${top}px`;
    wrap.style.left = `${Math.max(left, 12)}px`;
  };

  const openCalendar = (input) => {
    state.activeInput = input;
    const parsed = parseDate(input.value);
    const base = parsed ? new Date(parsed.year, parsed.month, parsed.day) : new Date();
    state.year = base.getFullYear();
    state.month = base.getMonth();
    render();
    positionCalendar(input);
    wrap.classList.add("open");
    wrap.setAttribute("aria-hidden", "false");
  };

  const closeCalendar = () => {
    wrap.classList.remove("open");
    wrap.setAttribute("aria-hidden", "true");
    state.activeInput = null;
  };

  prevBtn.addEventListener("click", () => {
    if (state.month === 0) {
      state.month = 11;
      state.year -= 1;
    } else {
      state.month -= 1;
    }
    render();
  });

  nextBtn.addEventListener("click", () => {
    if (state.month === 11) {
      state.month = 0;
      state.year += 1;
    } else {
      state.month += 1;
    }
    render();
  });

  document.body.appendChild(wrap);

  inputs.forEach((input) => {
    input.setAttribute("autocomplete", "off");
    input.readOnly = true;
    input.addEventListener("focus", () => openCalendar(input));
    input.addEventListener("click", () => openCalendar(input));
  });

  document.querySelectorAll("[data-date-trigger]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-date-trigger");
      const input = document.getElementById(targetId);
      if (input && !input.disabled) openCalendar(input);
    });
  });

  document.addEventListener("click", (event) => {
    if (!wrap.classList.contains("open")) return;
    if (wrap.contains(event.target)) return;
    if (event.target.closest("input[type='date']")) return;
    if (event.target.closest("[data-date-trigger]")) return;
    closeCalendar();
  });

  window.addEventListener("resize", () => {
    if (state.activeInput) positionCalendar(state.activeInput);
  });
  window.addEventListener("scroll", () => {
    if (state.activeInput) positionCalendar(state.activeInput);
  });
};
