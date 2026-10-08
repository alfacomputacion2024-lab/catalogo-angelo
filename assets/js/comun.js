/* =========================================================
   CATALOGO ANGELO · comun.js
   Carrito de interés compartido por la portada y el catálogo.

   Sin servidor: la lista vive en el navegador (localStorage,
   clave "angelo-interes"), por eso funciona igual en la página
   de Python (Render) y en la versión página normal (hosting
   estático). El número de WhatsApp llega en data-wa del <body>:
   si está vacío, el botón de enviar queda oculto.
   ========================================================= */
'use strict';

(function () {
  var WA = (document.body.getAttribute('data-wa') || '').replace(/\D/g, '');
  var K = 'angelo-interes';

  var items = [];
  try { items = JSON.parse(localStorage.getItem(K) || '[]') || []; } catch (e) { items = []; }
  var idx = {};
  items.forEach(function (x) { idx[String(x.id)] = x; });

  var lista = document.getElementById('carLista');
  var cajon = document.getElementById('carrito');
  var sombra = document.getElementById('carSombra');
  var nCart = document.getElementById('cartN');
  var vBtn = document.getElementById('visorCart');
  var waBtn = document.getElementById('carWa');

  function guardar() { try { localStorage.setItem(K, JSON.stringify(items)); } catch (e) {} }
  function contar() { if (nCart) nCart.textContent = items.length; }

  function pintarBoton(card, on) {
    var b = card && card.querySelector('.fadd');
    if (!b) return;
    b.classList.toggle('on', !!on);
    b.textContent = on ? '✓ En el carrito' : '+ Interés';
  }
  function pintarVisor() {
    if (!vBtn) return;
    var a = window.__visorActual;
    if (!a) { vBtn.hidden = true; return; }
    vBtn.hidden = false;
    var on = !!idx[String(a.id)];
    vBtn.classList.toggle('on', on);
    vBtn.textContent = on ? '✓ En el carrito de interés' : '+ Agregar al carrito de interés';
  }
  function pintarLista() {
    if (!lista) return;
    if (!items.length) {
      lista.innerHTML = '<div class="carrito-vacio">Tu carrito está vacío.<br>' +
        'Tocá «+ Interés» en los relojes que querés cotizar.</div>';
      return;
    }
    lista.textContent = '';
    items.forEach(function (x) {
      var f = document.createElement('div'); f.className = 'ci';
      var d = document.createElement('div');
      var b = document.createElement('b');
      b.textContent = (x.marca ? x.marca + ' · ' : '') + (x.ref || x.name || '');
      var s = document.createElement('small'); s.textContent = x.name || x.marca || '';
      d.appendChild(b); d.appendChild(s);
      var q = document.createElement('button'); q.type = 'button'; q.className = 'quitar';
      q.textContent = 'Quitar';
      q.onclick = function () { quitar(x.id); };
      f.appendChild(d); f.appendChild(q);
      lista.appendChild(f);
    });
    var t = document.createElement('div'); t.className = 'carrito-n';
    t.textContent = items.length + (items.length === 1 ? ' modelo seleccionado' : ' modelos seleccionados');
    lista.appendChild(t);
  }
  function agregar(o) {
    var id = String(o.id);
    if (idx[id]) return;
    var x = { id: o.id, ref: o.ref || '', name: o.name || '', marca: o.marca || '' };
    items.push(x); idx[id] = x;
    pintarBoton(document.querySelector('.card[data-id="' + o.id + '"]'), true);
    contar(); pintarLista(); pintarVisor(); guardar();
  }
  function quitar(id) {
    var s = String(id);
    items = items.filter(function (x) { return String(x.id) !== s; });
    delete idx[s];
    pintarBoton(document.querySelector('.card[data-id="' + id + '"]'), false);
    contar(); pintarLista(); pintarVisor(); guardar();
  }
  function alternar(o) { idx[String(o.id)] ? quitar(o.id) : agregar(o); }

  /* Botón «+ Interés» inyectado en cada tarjeta (no engorda el HTML) */
  [].forEach.call(document.querySelectorAll('.card'), function (c) {
    var b = document.createElement('button');
    b.type = 'button';
    var on = !!idx[c.dataset.id];
    b.className = 'fadd' + (on ? ' on' : '');
    b.textContent = on ? '✓ En el carrito' : '+ Interés';
    (c.querySelector('.card-body') || c).appendChild(b);
  });

  /* Clic en «+ Interés»: alterna y NO debe abrir la ficha */
  document.addEventListener('click', function (e) {
    var b = e.target.closest ? e.target.closest('.fadd') : null;
    if (!b) return;
    var card = b.closest('.card');
    if (!card) return;
    alternar({
      id: card.dataset.id,
      ref: ((card.querySelector('.ref') || {}).textContent || '').trim(),
      name: ((card.querySelector('.name') || {}).textContent || '').trim(),
      marca: card.dataset.brand || ''
    });
  });

  /* Cajón del carrito */
  function abrir() {
    if (!cajon) return;
    cajon.classList.add('on');
    if (sombra) sombra.classList.add('on');
    cajon.setAttribute('aria-hidden', 'false');
    pintarLista();
  }
  function cerrar() {
    if (!cajon) return;
    cajon.classList.remove('on');
    if (sombra) sombra.classList.remove('on');
    cajon.setAttribute('aria-hidden', 'true');
  }
  var cartNav = document.getElementById('cartNav');
  if (cartNav) cartNav.onclick = abrir;
  var carCerrar = document.getElementById('carCerrar');
  if (carCerrar) carCerrar.onclick = cerrar;
  if (sombra) sombra.onclick = cerrar;
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') cerrar(); });

  /* Mensaje armado solo para WhatsApp / copiar */
  function mensaje() {
    var l = ['Hola Angelo 👋, me interesan estos relojes:', ''];
    items.forEach(function (x, i) {
      l.push((i + 1) + '. ' + (x.marca ? x.marca + ' · ' : '') + (x.ref || x.name || ''));
    });
    l.push('', '¿Cuánto salen? ¡Gracias!');
    return l.join('\n');
  }
  if (WA && waBtn) {
    waBtn.hidden = false;
    waBtn.onclick = function () {
      window.open('https://wa.me/' + WA + '?text=' + encodeURIComponent(mensaje()), '_blank');
    };
  }
  var carCopiar = document.getElementById('carCopiar');
  if (carCopiar) carCopiar.onclick = function () {
    var btn = this;
    function listo() { btn.textContent = '¡Copiado!'; setTimeout(function () { btn.textContent = 'Copiar lista'; }, 1600); }
    function fallback() {
      var ta = document.createElement('textarea'); ta.value = mensaje();
      document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); listo(); } catch (e) {}
      document.body.removeChild(ta);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(mensaje()).then(listo, fallback);
    } else { fallback(); }
  };
  var carVaciar = document.getElementById('carVaciar');
  if (carVaciar) carVaciar.onclick = function () {
    if (!items.length) return;
    if (!confirm('¿Vaciar el carrito de interés?')) return;
    items = []; idx = {};
    [].forEach.call(document.querySelectorAll('.card'), function (c) { pintarBoton(c, false); });
    contar(); pintarLista(); pintarVisor(); guardar();
  };

  /* Botón dentro de la ficha (visor) */
  if (vBtn) vBtn.onclick = function () { var a = window.__visorActual; if (a) alternar(a); };

  /* La galería avisa cuando cambia el producto abierto */
  window.angeloCarrito = { visor: pintarVisor };

  contar(); pintarLista(); pintarVisor();
})();
