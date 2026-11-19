/* Alcalde Digital: comportamiento del sitio. Sin dependencias ni rastreadores. */
(function () {
  "use strict";

  // ---- Pestañas accesibles (minijuegos y sistema operativo) ----
  function pestanas(lista, panelesDe, vertical) {
    var tabs = Array.prototype.slice.call(lista.querySelectorAll('[role="tab"]'));
    function elegir(tab, enfocar) {
      tabs.forEach(function (t) {
        var activa = t === tab;
        t.setAttribute("aria-selected", activa ? "true" : "false");
        t.tabIndex = activa ? 0 : -1;
        var panel = document.getElementById(t.getAttribute("aria-controls"));
        if (panel) { panel.hidden = !activa; }
      });
      if (enfocar) { tab.focus(); }
    }
    tabs.forEach(function (t, i) {
      t.addEventListener("click", function () { elegir(t, false); });
      t.addEventListener("keydown", function (e) {
        var vert = typeof vertical === "function" ? vertical() : vertical;
        var sig = vert ? "ArrowDown" : "ArrowRight", ant = vert ? "ArrowUp" : "ArrowLeft";
        var destino = null;
        if (e.key === sig || e.key === "ArrowDown" && !vert || e.key === "ArrowRight" && vert) { destino = tabs[(i + 1) % tabs.length]; }
        else if (e.key === ant || e.key === "ArrowUp" && !vert || e.key === "ArrowLeft" && vert) { destino = tabs[(i - 1 + tabs.length) % tabs.length]; }
        else if (e.key === "Home") { destino = tabs[0]; }
        else if (e.key === "End") { destino = tabs[tabs.length - 1]; }
        if (destino) { e.preventDefault(); elegir(destino, true); }
      });
    });
    return { elegir: elegir, tabs: tabs };
  }

  var listaMini = document.querySelector(".mini-lista");
  var consultaFila = window.matchMedia("(max-width: 1020px)");
  if (listaMini) {
    pestanas(listaMini, null, function () { return !consultaFila.matches; });
    var orientar = function () { listaMini.setAttribute("aria-orientation", consultaFila.matches ? "horizontal" : "vertical"); };
    orientar();
    if (consultaFila.addEventListener) { consultaFila.addEventListener("change", orientar); }
  }

  var listaSO = document.querySelector(".so");
  if (listaSO) {
    var so = pestanas(listaSO, null, false);
    var plataforma = (navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || navigator.userAgent || "";
    var esLinux = /linux|x11/i.test(plataforma) && !/android/i.test(navigator.userAgent);
    var esMac = /mac/i.test(plataforma) && !/iphone|ipad/i.test(navigator.userAgent);
    var id = esMac ? "so-mac" : (esLinux ? "so-lin" : "so-win");
    var tab = document.getElementById(id);
    var recomendado = document.getElementById(id === "so-mac" ? "dl-mac" : (id === "so-lin" ? "dl-lin" : "dl-win"));
    if (recomendado) { recomendado.classList.add("recomendado"); }
    if (tab) { so.elegir(tab, false); }
  }

  // ---- Comparador de la ciudad ----
  var marco = document.getElementById("marco-comparador");
  var rango = document.getElementById("comp-rango");
  var tapa = document.getElementById("comp-crisis");
  var base = document.getElementById("comp-florece");
  var linea = document.getElementById("comp-linea");
  var PARES = {
    fuente: { crisis: "img/viva-crisis-fuente.jpg", florece: "img/viva-florece-fuente.jpg",
      altCrisis: "La fuente en crisis: cielo apagado, basura en el suelo y la plaza vacía",
      altFlorece: "La fuente cuando la ciudad florece: banderines, flores y vecinos conversando" },
    plaza: { crisis: "img/viva-crisis-plaza.jpg", florece: "img/viva-florece-plaza.jpg",
      altCrisis: "La plaza del parque en crisis: papeles y basura, farolas apagadas y nadie en la plaza",
      altFlorece: "La plaza del parque cuando la ciudad florece: banderines, flores y un corro de vecinos" }
  };
  function poner(valor) {
    valor = Math.max(0, Math.min(100, valor));
    tapa.style.clipPath = "inset(0 " + (100 - valor) + "% 0 0)";
    linea.style.left = valor + "%";
    rango.value = String(valor);
  }
  if (marco && rango) {
    rango.addEventListener("input", function () { poner(Number(rango.value)); });
    var arrastrando = false;
    function desdePuntero(e) {
      var r = marco.getBoundingClientRect();
      poner(((e.clientX - r.left) / r.width) * 100);
    }
    marco.addEventListener("pointerdown", function (e) { arrastrando = true; marco.setPointerCapture(e.pointerId); desdePuntero(e); });
    marco.addEventListener("pointermove", function (e) { if (arrastrando) { desdePuntero(e); } });
    marco.addEventListener("pointerup", function () { arrastrando = false; });
    marco.addEventListener("pointercancel", function () { arrastrando = false; });
    document.querySelectorAll("[data-par]").forEach(function (b) {
      b.addEventListener("click", function () {
        var par = PARES[b.getAttribute("data-par")];
        if (!par) { return; }
        tapa.src = par.crisis; tapa.alt = par.altCrisis;
        base.src = par.florece; base.alt = par.altFlorece;
        document.querySelectorAll("[data-par]").forEach(function (o) { o.setAttribute("aria-pressed", o === b ? "true" : "false"); });
      });
    });
    poner(50);
  }

  // ---- Galería ----
  var galeria = document.getElementById("galeria");
  function paso(dir) {
    var f = galeria.querySelector("figure");
    var ancho = f ? f.getBoundingClientRect().width + 22 : 400;
    var quieto = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    galeria.scrollBy({ left: dir * ancho, behavior: quieto ? "auto" : "smooth" });
  }
  if (galeria) {
    document.getElementById("gal-prev").addEventListener("click", function () { paso(-1); });
    document.getElementById("gal-sig").addEventListener("click", function () { paso(1); });
    var figuras = galeria.querySelectorAll("figure");
    var estado = document.getElementById("gal-estado");
    var anunciar = function () {
      var centro = galeria.scrollLeft + galeria.clientWidth / 2, mejor = 0, dist = 1e9;
      figuras.forEach(function (f, i) { var d = Math.abs(f.offsetLeft + f.offsetWidth / 2 - centro); if (d < dist) { dist = d; mejor = i; } });
      if (estado) { estado.textContent = "Imagen " + (mejor + 1) + " de " + figuras.length; }
    };
    var temporizador = null;
    galeria.addEventListener("scroll", function () { clearTimeout(temporizador); temporizador = setTimeout(anunciar, 250); });
    galeria.addEventListener("keydown", function (e) {
      if (e.key === "ArrowRight") { e.preventDefault(); paso(1); }
      if (e.key === "ArrowLeft") { e.preventDefault(); paso(-1); }
    });
  }

  // ---- Visor de imágenes ----
  var ultimoDisparador = null;
  document.querySelectorAll("img[data-zoom]").forEach(function (img) {
    img.tabIndex = 0;
    img.setAttribute("role", "button");
    img.setAttribute("aria-label", "Ampliar imagen: " + (img.alt || ""));
    img.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); abrir(img); } });
  });
  var visor = document.getElementById("visor");
  var visorImg = document.getElementById("visor-img");
  var visorPie = document.getElementById("visor-pie");
  function abrir(img) {
    ultimoDisparador = img;
    visorImg.src = img.currentSrc || img.src;
    visorImg.alt = img.alt || "";
    var fig = img.closest("figure");
    var leyenda = fig && fig.querySelector("figcaption");
    visorPie.textContent = leyenda ? leyenda.textContent : (img.alt || "");
    if (typeof visor.showModal === "function") { visor.showModal(); }
  }
  document.addEventListener("click", function (e) {
    var img = e.target.closest && e.target.closest("img[data-zoom]");
    if (img) { abrir(img); }
  });
  if (visor) {
    visor.addEventListener("click", function (e) { if (e.target === visor) { visor.close(); } });
    visor.addEventListener("close", function () { if (ultimoDisparador) { ultimoDisparador.focus(); } });
  }

  // ---- Copiar comandos ----
  document.querySelectorAll("[data-copiar]").forEach(function (b) {
    b.addEventListener("click", function () {
      var texto = b.getAttribute("data-copiar");
      var listo = function () { var antes = b.textContent; b.textContent = "Copiado"; var av = document.getElementById("aviso-copiado"); if (av) { av.textContent = "Comando copiado"; } setTimeout(function () { b.textContent = antes; if (av) { av.textContent = ""; } }, 1400); };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(texto).then(listo, function () { seleccionar(b); });
      } else { seleccionar(b); }
    });
  });
  function seleccionar(b) {
    var code = b.parentNode.querySelector("code");
    if (!code) { return; }
    var r = document.createRange(); r.selectNodeContents(code);
    var s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
  }
})();
