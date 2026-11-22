// Hostly – kleine Helfer. Alles funktioniert auch ohne JavaScript.

document.addEventListener("DOMContentLoaded", () => {
  // Hell/Dunkel sofort umschalten (ohne Neuladen) und im Hintergrund speichern.
  const themeForm = document.querySelector(".theme-form");
  if (themeForm) {
    themeForm.addEventListener("submit", (event) => {
      event.preventDefault();
      const root = document.documentElement;
      const current = root.dataset.theme
        || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
      const next = current === "dark" ? "light" : "dark";
      root.dataset.theme = next;
      const data = new FormData(themeForm);
      data.set("theme", next);
      fetch(themeForm.action, { method: "POST", body: data, headers: { "X-Requested-With": "fetch" } });
    });
  }

  // Menü schließen, wenn man daneben klickt
  document.addEventListener("click", (event) => {
    document.querySelectorAll("details.menu[open]").forEach((menu) => {
      if (!menu.contains(event.target)) menu.removeAttribute("open");
    });
  });

  // Kopieren-Knöpfe
  document.addEventListener("click", async (event) => {
    const btn = event.target.closest("[data-copy]");
    if (!btn) return;
    try {
      await navigator.clipboard.writeText(btn.dataset.copy);
      const old = btn.textContent;
      btn.textContent = "✓";
      setTimeout(() => { btn.textContent = old; }, 1200);
    } catch (e) { prompt("Kopieren:", btn.dataset.copy); }
  });

  setupCroppers();
  setupMotdEditor();
  scrollConsoles();
});

// Konsole automatisch nach unten scrollen (auch nach HTMX-Aktualisierung)
function scrollConsoles() {
  document.querySelectorAll("[data-autoscroll]").forEach((el) => { el.scrollTop = el.scrollHeight; });
}
document.addEventListener("htmx:beforeSwap", (e) => {
  const pre = e.detail.target.querySelector && e.detail.target.querySelector("[data-autoscroll]");
  if (pre) e.detail.target.dataset.atBottom = (pre.scrollHeight - pre.scrollTop - pre.clientHeight < 40) ? "1" : "0";
});
document.addEventListener("htmx:afterSwap", (e) => {
  if (e.detail.target.dataset.atBottom !== "0") {
    const pre = e.detail.target.querySelector && e.detail.target.querySelector("[data-autoscroll]");
    if (pre) pre.scrollTop = pre.scrollHeight;
  }
});

// Bild-Zuschnitt (Server-Icon, Profilbild): Rahmen verschieben + zoomen, quadratisch
function setupCroppers() {
  document.querySelectorAll("form[data-cropper]").forEach((form) => {
    const input = form.querySelector('input[type="file"]');
    const area = form.querySelector(".crop-area");
    const img = area && area.querySelector("img");
    if (!input || !img || typeof Cropper === "undefined") return;
    let cropper = null;
    input.addEventListener("change", () => {
      const file = input.files && input.files[0];
      if (!file) return;
      const own = form.querySelector('input[name="mode"][value="own"]');
      if (own) own.checked = true;
      img.src = URL.createObjectURL(file);
      area.hidden = false;
      if (cropper) cropper.destroy();
      cropper = new Cropper(img, { aspectRatio: 1, viewMode: 1, dragMode: "move", autoCropArea: 1 });
    });
    form.addEventListener("submit", (event) => {
      if (!cropper) return;
      event.preventDefault();
      cropper.getCroppedCanvas({ width: 256, height: 256 }).toBlob((blob) => {
        const dt = new DataTransfer();
        dt.items.add(new File([blob], "bild.png", { type: "image/png" }));
        input.files = dt.files;
        cropper.destroy(); cropper = null;
        form.submit();
      }, "image/png");
    });
  });
}

// MOTD-Editor: Farbknöpfe + Live-Vorschau im Minecraft-Stil
const MC_COLORS = { 0: "#000000", 1: "#0000AA", 2: "#00AA00", 3: "#00AAAA", 4: "#AA0000", 5: "#AA00AA", 6: "#FFAA00", 7: "#AAAAAA", 8: "#555555", 9: "#5555FF", a: "#55FF55", b: "#55FFFF", c: "#FF5555", d: "#FF55FF", e: "#FFFF55", f: "#FFFFFF" };
const MC_FORMATS = { l: "font-weight:bold", o: "font-style:italic", n: "text-decoration:underline", m: "text-decoration:line-through" };

function motdToHtml(text) {
  const out = [];
  let color = "#AAAAAA", styles = [], buf = "";
  const esc = (s) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const flush = () => { if (buf) { out.push(`<span style="${["color:" + color, ...styles].join(";")}">${esc(buf)}</span>`); buf = ""; } };
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch === "§" && i + 1 < text.length) {
      const code = text[i + 1].toLowerCase(); flush();
      if (MC_COLORS[code]) { color = MC_COLORS[code]; styles = []; }
      else if (MC_FORMATS[code]) styles.push(MC_FORMATS[code]);
      else if (code === "r") { color = "#AAAAAA"; styles = []; }
      i++; continue;
    }
    if (ch === "\n") { flush(); out.push("<br>"); } else buf += ch;
  }
  flush();
  return out.join("");
}

function setupMotdEditor() {
  const text = document.getElementById("motd-text");
  const preview = document.getElementById("motd-preview");
  if (!text || !preview) return;
  const update = () => { preview.innerHTML = motdToHtml(text.value); };
  text.addEventListener("input", update);
  document.querySelectorAll(".motd-buttons [data-code]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const ins = "§" + btn.dataset.code;
      const s = text.selectionStart, e = text.selectionEnd;
      text.value = text.value.slice(0, s) + ins + text.value.slice(e);
      text.focus(); text.selectionStart = text.selectionEnd = s + ins.length;
      update();
    });
  });
}
