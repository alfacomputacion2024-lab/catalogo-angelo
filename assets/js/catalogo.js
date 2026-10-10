/* =========================================================
   CATALOGO ANGELO · catalogo.js
   Comportamiento del catálogo de clientes:
   filtros al instante (marca / texto / tipo / favoritos),
   favoritos, ficha ampliada (visor) y píldoras que llevan
   a las páginas de cada marca.

   La configuración de la página llega en los atributos
   data-* del <body>: data-pag (total | marca | tipo),
   data-marca, data-tipo, data-estatico y data-ruta-catalogo.

   Las píldoras son enlaces de verdad: en las páginas de marca
   y tipo navegan a otra página; en el catálogo completo
   (data-pag="total") se interceptan para filtrar al instante
   sin recargar.
   ========================================================= */
'use strict';

(function () {
  var body = document.body;
  var PAG = body.getAttribute('data-pag') || 'total';
  var RUTA_CATALOGO = body.getAttribute('data-ruta-catalogo') || '/catalogo';
  var ESTATICO = body.getAttribute('data-estatico') === '1';

  var cards = [].slice.call(document.querySelectorAll('.card'));
  var secciones = [].slice.call(document.querySelectorAll('section.brand'));
  var buscador = document.getElementById('buscador');
  var contador = document.getElementById('contador');
  var vacio = document.getElementById('vacio');
  var pills = [].slice.call(document.querySelectorAll('.pill[data-marca]'));
  var genPills = [].slice.call(document.querySelectorAll('.pill[data-genero]'));
  var genChip = document.getElementById('genChip');
  var favNav = document.getElementById('favNav');
  var favN = document.getElementById('favN');
  var migaSep = document.getElementById('migaSep');
  var migaMarca = document.getElementById('migaMarca');
  var migaSepT = document.getElementById('migaSepT');
  var migaTipo = document.getElementById('migaTipo');
  var colec = document.getElementById('colecciones');
  var tipoChip = document.getElementById('tipoChip');
  /* La página viene ya filtrada (marca/tipo) desde el servidor */
  var marca = body.getAttribute('data-marca') || '';
  var tipo = body.getAttribute('data-tipo') || '';
  var genero = '';      /* '' = todos · 'Hombre' | 'Dama' (se ve "Mujer") | 'Unisex' */
  var soloFavs = false;

  /* ----- Tipo de producto: MISMO criterio que _coincide_tipo() de app.py
          (el conteo de la portada y el filtro del catálogo deben coincidir) ----- */
  function coincideTipo(c) {
    if (!tipo) return true;
    var linea = (c.dataset.linea || '').toLowerCase().replace(/\s+/g, '');
    var gen = (c.dataset.genero || '').toLowerCase();
    if (tipo === 'G-Shock') return linea.indexOf('g-shock') >= 0;
    if (tipo === 'Baby-G') return linea.indexOf('baby-g') >= 0;
    if (tipo === 'Edifice') return linea.indexOf('edifice') >= 0;
    if (tipo === 'Pro Trek') return linea.indexOf('protrek') >= 0;
    if (tipo === 'Dama') return gen === 'dama' || linea.indexOf('dama') >= 0;
    return true;
  }

  /* Texto del chip: en la base el género de mujer está guardado como "Dama" */
  function etiquetaGenero(g) { return g === 'Dama' ? 'Mujer' : g; }

  /* ----- Favoritos: guardados en el navegador (sin cuenta, sin servidor) ----- */
  var KF = 'angelo-favs', favs = [];
  try { favs = JSON.parse(localStorage.getItem(KF) || '[]') || []; } catch (e) { favs = []; }
  var favSet = {};
  favs.forEach(function (id) { favSet[String(id)] = 1; });
  cards.forEach(function (c) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'fb' + (favSet[c.dataset.id] ? ' on' : '');
    b.setAttribute('aria-label', 'Guardar en favoritos');
    b.textContent = '♥';
    c.appendChild(b);
  });
  function pintarFavs() {
    if (favN) favN.textContent = favs.length;
    if (favNav) {
      favNav.classList.toggle('sel', soloFavs);
      favNav.title = soloFavs ? 'Mostrar todo' : 'Ver solo tus favoritos';
    }
  }
  /* El clic del corazón se resuelve ANTES de llegar al documento:
     no abre la ficha del reloj (stopPropagation) */
  document.addEventListener('click', function (e) {
    var b = e.target.closest ? e.target.closest('.fb') : null;
    if (!b) return;
    e.stopPropagation();
    var id = b.parentElement.dataset.id;
    if (favSet[id]) {
      favs = favs.filter(function (x) { return String(x) !== id; });
      delete favSet[id]; b.classList.remove('on');
    } else {
      favs.push(id); favSet[id] = 1; b.classList.add('on');
    }
    try { localStorage.setItem(KF, JSON.stringify(favs)); } catch (e2) {}
    pintarFavs();
    if (soloFavs) aplicar();
  });
  if (favNav) favNav.onclick = function () {
    soloFavs = !soloFavs; pintarFavs(); aplicar();
    var cat = document.getElementById('catalogo');
    if (cat) cat.scrollIntoView({ behavior: 'smooth' });
  };

  /* ----- Filtrado combinado: marca + texto + favoritos + tipo ----- */
  function aplicar() {
    var q = ((buscador && buscador.value) || '').toLowerCase().trim();
    var vis = 0;
    cards.forEach(function (c) {
      var ok = (!marca || c.dataset.brand === marca)
        && (!q || c.dataset.busqueda.indexOf(q) >= 0)
        && (!soloFavs || favSet[c.dataset.id])
        && (!genero || (c.dataset.genero || 'Unisex') === genero)
        && coincideTipo(c);
      c.hidden = !ok;
      if (ok) vis++;
    });
    secciones.forEach(function (s) {
      var hay = [].some.call(s.querySelectorAll('.card'), function (c) { return !c.hidden; });
      s.hidden = !hay;
    });
    if (contador) contador.textContent = vis + ' ' + (vis === 1 ? 'producto' : 'productos');
    if (vacio) {
      vacio.textContent = (soloFavs && !favs.length)
        ? 'Todavía no guardaste favoritos — tocá el ♥ de cualquier reloj.'
        : 'Sin resultados — probá con otra referencia o marca.';
      vacio.hidden = vis > 0;
    }
    /* Migas: tipo y marca cuando hay filtros activos */
    if (migaSepT && migaTipo) {
      migaSepT.hidden = !tipo;
      migaTipo.textContent = tipo;
    }
    if (migaSep && migaMarca) {
      migaSep.hidden = !marca;
      migaMarca.textContent = marca;
    }
    /* Chip para quitar el tipo de producto */
    if (tipoChip) {
      tipoChip.hidden = !tipo;
      if (tipo) tipoChip.textContent = 'Tipo: ' + tipo + ' ✕';
    }
    /* Chip para quitar el filtro de género */
    if (genChip) {
      genChip.hidden = !genero;
      if (genero) genChip.textContent = 'Género: ' + etiquetaGenero(genero) + ' ✕';
    }
    /* Las colecciones solo caben en la vista completa */
    if (colec) colec.hidden = !(!marca && !q && !soloFavs && !tipo && !genero);
    /* Píldora de marca marcada como activa */
    pills.forEach(function (p) { p.classList.toggle('sel', p.dataset.marca === marca); });
    genPills.forEach(function (p) { p.classList.toggle('sel', (p.dataset.genero || '') === genero); });
    /* URL compartible (sólo en el catálogo completo) */
    if (PAG === 'total' && window.history && window.history.replaceState) {
      var qs = [];
      if (q) qs.push('q=' + encodeURIComponent(q));
      if (marca) qs.push('marca=' + encodeURIComponent(marca));
      if (tipo) qs.push('tipo=' + encodeURIComponent(tipo));
      if (genero) qs.push('genero=' + encodeURIComponent(genero));
      try { window.history.replaceState(null, '', RUTA_CATALOGO + (qs.length ? '?' + qs.join('&') : '')); } catch (e) {}
    }
  }

  /* ----- Píldoras de marca (son enlaces reales) ----- */
  pills.forEach(function (a) {
    a.addEventListener('click', function (e) {
      if (PAG !== 'total') return;        /* página de marca/tipo: navega normal */
      e.preventDefault();
      marca = a.dataset.marca;
      aplicar();
    });
  });
  /* ----- Píldoras de género: al instante en TODAS las páginas
          (no hay página por género: sólo filtra lo que ya se está viendo) ----- */
  genPills.forEach(function (a) {
    a.addEventListener('click', function () {
      genero = a.dataset.genero || '';
      aplicar();
    });
  });
  /* Tarjetas de colección -> activan su píldora de marca y bajan al catálogo */
  [].forEach.call(document.querySelectorAll('.colec-tile'), function (t) {
    t.addEventListener('click', function (e) {
      if (PAG !== 'total') return;
      e.preventDefault();
      marca = t.dataset.tile || '';
      aplicar();
      var cat = document.getElementById('catalogo');
      if (cat) cat.scrollIntoView({ behavior: 'smooth' });
    });
  });

  /* Buscador: 120 ms de espera (en el celular cada tecla repintaba 3.000+ tarjetas) */
  if (buscador) {
    var t = null;
    buscador.addEventListener('input', function () { clearTimeout(t); t = setTimeout(aplicar, 120); });
    var form = buscador.closest('form');
    if (form) form.addEventListener('submit', function (e) { e.preventDefault(); aplicar(); });
  }
  /* Chip del tipo: al tocarlo se quita ese filtro */
  if (tipoChip) tipoChip.onclick = function () { tipo = ''; aplicar(); };
  /* Chip del género: al tocarlo se quita ese filtro */
  if (genChip) genChip.onclick = function () { genero = ''; aplicar(); };

  /* ----- La URL manda filtros: ?q= / ?marca= / ?tipo= / ?abrir= -----
     Se lee ANTES de aplicar(): al filtrar, aplicar() limpia la URL con
     replaceState y estos parámetros dejarían de existir. */
  var abrirCon = null;
  try {
    var qs = new URLSearchParams(location.search);
    var t0 = qs.get('tipo') || '';
    if (t0) tipo = t0;
    var m0 = qs.get('marca') || '';
    if (m0 && PAG === 'total') marca = m0;
    var b0 = qs.get('q') || '';
    if (b0 && buscador) buscador.value = b0;
    var g0 = (qs.get('genero') || '').toLowerCase();
    if (g0 === 'hombre') genero = 'Hombre';
    else if (g0 === 'dama' || g0 === 'mujer') genero = 'Dama';
    else if (g0 === 'unisex') genero = 'Unisex';
    var a0 = qs.get('abrir') || '';
    if (a0 && /^[0-9]+$/.test(a0)) abrirCon = a0;   // enlace directo a un producto
  } catch (e) {}

  pintarFavs();
  aplicar();

  /* =========================================================
     Visor (galería): tocar un modelo abre todas sus fotos
     La ficha sale de /api/ficha/<id> (Python) o
     /api/ficha/<id>.json (página normal) según data-estatico.
     ========================================================= */
  var visor = document.getElementById('visor');
  if (visor) {
    var vImg = document.getElementById('visorImg');
    var vEst = document.getElementById('visorEstado');
    var vCont = document.getElementById('visorCont');
    var vMini = document.getElementById('visorMini');
    var vMarca = document.getElementById('visorMarca');
    var vRef = document.getElementById('visorRef');
    var vNom = document.getElementById('visorNombre');
    var vSpecs = document.getElementById('visorSpecs');
    var fotos = [], iF = 0, cargando = null;

    function pintarFotos() {
      if (!fotos.length) { vImg.hidden = true; vCont.hidden = true; return; }
      vImg.src = fotos[iF];
      vImg.hidden = false;
      vEst.hidden = true;
      vCont.hidden = false;
      vCont.textContent = (iF + 1) + ' / ' + fotos.length;
      [].forEach.call(vMini.children, function (elm, k) { elm.classList.toggle('sel', k === iF); });
    }
    function mover(d) {
      if (!fotos.length) return;
      iF = (iF + d + fotos.length) % fotos.length;
      pintarFotos();
    }
    function abrirFicha(id) {
      visor.classList.add('on');
      visor.setAttribute('aria-hidden', 'false');
      document.body.style.overflow = 'hidden';
      fotos = []; iF = 0;
      vImg.hidden = true; vCont.hidden = true; vMini.innerHTML = '';
      vEst.hidden = false; vEst.textContent = 'Cargando…';
      vMarca.textContent = ''; vRef.textContent = ''; vNom.textContent = ''; vSpecs.innerHTML = '';
      window.__visorActual = null;
      if (window.angeloCarrito) window.angeloCarrito.visor();
      if (cargando && cargando.abort) cargando.abort();
      cargando = fetch('/api/ficha/' + id + (ESTATICO ? '.json' : ''))
        .then(function (r) { if (!r.ok) throw 0; return r.json(); })
        .then(function (p) {
          vMarca.textContent = p.marca || '';
          vRef.textContent = p.reference || '';
          vNom.textContent = (p.name || '').toUpperCase();
          window.__visorActual = { id: p.id, ref: p.reference || '', name: p.name || '', marca: p.marca || '' };
          if (window.angeloCarrito) window.angeloCarrito.visor();
          fotos = p.images || [];
          var claves = Object.keys(p.specs || {});
          if (claves.length) {
            claves.forEach(function (k) {
              var d = document.createElement('div');
              var b = document.createElement('b');
              b.textContent = k;
              d.appendChild(b);
              d.appendChild(document.createTextNode(p.specs[k]));
              vSpecs.appendChild(d);
            });
          } else {
            vSpecs.innerHTML = '<div class="sin-specs">Sin datos técnicos disponibles.</div>';
          }
          if (!fotos.length) {
            vEst.hidden = false; vEst.textContent = 'Sin fotos disponibles.';
            return;
          }
          fotos.forEach(function (u, k) {
            var th = document.createElement('img');
            th.loading = 'lazy'; th.src = u; th.alt = (p.reference || '') + ' ' + (k + 1);
            th.onclick = function () { iF = k; pintarFotos(); };
            vMini.appendChild(th);
          });
          iF = 0; pintarFotos();
        })
        .catch(function () {
          vEst.hidden = false;
          vEst.textContent = 'No se pudo cargar la ficha. Probá de nuevo.';
        });
    }
    function cerrarFicha() {
      visor.classList.remove('on');
      visor.setAttribute('aria-hidden', 'true');
      document.body.style.overflow = '';
      window.__visorActual = null;
      if (window.angeloCarrito) window.angeloCarrito.visor();
    }

    document.addEventListener('click', function (e) {
      if (e.target.closest && e.target.closest('.fb,.fadd')) return;  /* corazón e «+ Interés» no abren la ficha */
      var c = e.target.closest ? e.target.closest('.card[data-id]') : null;
      if (c) abrirFicha(c.dataset.id);
    });
    document.getElementById('visorCerrar').onclick = cerrarFicha;
    document.getElementById('visorPrev').onclick = function () { mover(-1); };
    document.getElementById('visorNext').onclick = function () { mover(1); };
    visor.addEventListener('click', function (e) { if (e.target === visor) cerrarFicha(); });
    document.addEventListener('keydown', function (e) {
      if (!visor.classList.contains('on')) return;
      if (e.key === 'Escape') cerrarFicha();
      if (e.key === 'ArrowLeft') mover(-1);
      if (e.key === 'ArrowRight') mover(1);
    });
    /* Swipe en celular */
    var x0 = null;
    visor.addEventListener('touchstart', function (e) { x0 = e.touches[0].clientX; }, { passive: true });
    visor.addEventListener('touchend', function (e) {
      if (x0 === null) return;
      var dx = e.changedTouches[0].clientX - x0;
      if (Math.abs(dx) > 45) mover(dx < 0 ? 1 : -1);
      x0 = null;
    }, { passive: true });

    /* Enlace directo a un producto: /catalogo.html?abrir=<id>
       (sirve para compartir un modelo o para abrirlo desde la portada) */
    if (abrirCon) abrirFicha(abrirCon);
  }
})();
