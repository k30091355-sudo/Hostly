// Hostly – kleine Helfer. Alles funktioniert auch ohne JavaScript.

// Hell/Dunkel sofort umschalten (ohne Neuladen) und im Hintergrund speichern.
document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector(".theme-form");
  if (!form) return;
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const root = document.documentElement;
    const current = root.dataset.theme
      || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = current === "dark" ? "light" : "dark";
    root.dataset.theme = next;
    const data = new FormData(form);
    data.set("theme", next);
    fetch(form.action, { method: "POST", body: data, headers: { "X-Requested-With": "fetch" } });
  });

  // Menü schließen, wenn man daneben klickt
  document.addEventListener("click", (event) => {
    document.querySelectorAll("details.menu[open]").forEach((menu) => {
      if (!menu.contains(event.target)) menu.removeAttribute("open");
    });
  });
});
