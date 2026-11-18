"use strict";

// Conferma prima di ogni eliminazione (form con classe .elimina)
document.querySelectorAll("form.elimina").forEach((form) => {
  form.addEventListener("submit", (evento) => {
    const nome = form.dataset.nome || "questo elemento";
    if (!confirm(`Eliminare definitivamente ${nome}?`)) {
      evento.preventDefault();
    }
  });
});

// Avvisi che spariscono da soli
document.querySelectorAll(".avviso").forEach((avviso) => {
  setTimeout(() => {
    avviso.style.transition = "opacity .4s";
    avviso.style.opacity = "0";
    setTimeout(() => avviso.remove(), 400);
  }, 5000);
});

// Filtro live sulla griglia prodotti
const filtro = document.getElementById("filtro");
const griglia = document.getElementById("griglia-prodotti");
if (filtro && griglia) {
  filtro.addEventListener("input", () => {
    const testo = filtro.value.trim().toLowerCase();
    griglia.querySelectorAll(".prodotto").forEach((card) => {
      const corrisponde = (card.dataset.testo || "").includes(testo);
      card.style.display = corrisponde ? "" : "none";
    });
  });
}

// Misuratore di robustezza password
const password = document.getElementById("password");
const robustezza = document.getElementById("robustezza");
if (password && robustezza) {
  password.addEventListener("input", () => {
    const valore = password.value;
    let punteggio = 0;
    if (valore.length >= 8) punteggio++;
    if (/[A-Z]/.test(valore) && /[a-z]/.test(valore)) punteggio++;
    if (/[0-9]/.test(valore)) punteggio++;
    if (/[^A-Za-z0-9]/.test(valore)) punteggio++;
    robustezza.className = "";
    if (!valore) return;
    if (punteggio <= 1) robustezza.classList.add("debole");
    else if (punteggio === 2) robustezza.classList.add("media");
    else robustezza.classList.add("forte");
  });
}

// Pulsante torna su
const tornaSu = document.getElementById("torna-su");
if (tornaSu) {
  window.addEventListener("scroll", () => {
    tornaSu.classList.toggle("visibile", window.scrollY > 400);
  });
  tornaSu.addEventListener("click", () =>
    window.scrollTo({ top: 0, behavior: "smooth" })
  );
}