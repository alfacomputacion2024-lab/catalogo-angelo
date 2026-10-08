/* =========================================================
   CATALOGO ANGELO · tema.js
   Se carga en el <head> (antes de pintar) para aplicar el
   fondo elegido sin parpadeo, y después conecta los botones
   del selector de tema. Sin esto, la página se vería un
   instante en negro antes de pasar al color elegido.
   ========================================================= */
'use strict';

(function () {
  var K = 'angelo-tema';
  var t = null;
  try { t = localStorage.getItem(K); } catch (e) {}
  document.documentElement.setAttribute('data-tema', t || 'negro');

  document.addEventListener('DOMContentLoaded', function () {
    var actual = document.documentElement.getAttribute('data-tema') || 'negro';
    var botones = document.querySelectorAll('.temas button');
    function marcar() {
      botones.forEach(function (b) { b.classList.toggle('sel', b.dataset.tema === actual); });
    }
    marcar();
    botones.forEach(function (b) {
      b.onclick = function () {
        actual = b.dataset.tema;
        document.documentElement.setAttribute('data-tema', actual);
        try { localStorage.setItem(K, actual); } catch (e) {}
        marcar();
      };
    });
  });
})();
