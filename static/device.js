// NeuroScore — identificação do aparelho (antifraude do teste grátis).
// O navegador NÃO dá acesso ao endereço MAC; no lugar dele usamos:
//  • id  — código aleatório gravado neste navegador (localStorage + cookie, 2 anos);
//  • fp  — "impressão digital" do aparelho: tela, fuso, idioma, núcleos, memória,
//          placa de vídeo e desenho em canvas, resumidos num hash.
(function () {
  function h53(str) { // cyrb53: hash rápido e estável
    let a = 0xdeadbeef, b = 0x41c6ce57;
    for (let i = 0; i < str.length; i++) { const c = str.charCodeAt(i); a = Math.imul(a ^ c, 2654435761); b = Math.imul(b ^ c, 1597334677); }
    a = Math.imul(a ^ (a >>> 16), 2246822507) ^ Math.imul(b ^ (b >>> 13), 3266489909);
    b = Math.imul(b ^ (b >>> 16), 2246822507) ^ Math.imul(a ^ (a >>> 13), 3266489909);
    return (4294967296 * (2097151 & b) + (a >>> 0)).toString(36);
  }
  function canvasSig() {
    try {
      const c = document.createElement('canvas'); c.width = 240; c.height = 60; const x = c.getContext('2d');
      x.textBaseline = 'top'; x.font = '16px Arial'; x.fillStyle = '#f60'; x.fillRect(100, 1, 62, 20);
      x.fillStyle = '#069'; x.fillText('NeuroScore ✓ 2026', 2, 15); x.fillStyle = 'rgba(102,204,0,.7)'; x.fillText('NeuroScore ✓ 2026', 4, 17);
      return c.toDataURL();
    } catch { return ''; }
  }
  function gpu() {
    try {
      const g = document.createElement('canvas').getContext('webgl'); if (!g) return '';
      const e = g.getExtension('WEBGL_debug_renderer_info');
      return e ? `${g.getParameter(e.UNMASKED_VENDOR_WEBGL)}|${g.getParameter(e.UNMASKED_RENDERER_WEBGL)}` : String(g.getParameter(g.RENDERER));
    } catch { return ''; }
  }
  function fingerprint() {
    const n = navigator, s = screen;
    return h53([n.userAgent, n.platform, n.language, (n.languages || []).join(','), n.hardwareConcurrency, n.deviceMemory,
      n.maxTouchPoints, s.width + 'x' + s.height + 'x' + s.colorDepth, window.devicePixelRatio,
      Intl.DateTimeFormat().resolvedOptions().timeZone, gpu(), canvasSig()].join('§'));
  }
  function deviceId() {
    let id = '';
    try { id = localStorage.getItem('ns_device') || ''; } catch {}
    if (!id) { const m = document.cookie.match(/(?:^|; )ns_device=([A-Za-z0-9-]{8,64})/); if (m) id = m[1]; }
    if (!id) id = (crypto.randomUUID ? crypto.randomUUID() : h53(Math.random() + '' + Date.now()) + h53(String(performance.now())));
    try { localStorage.setItem('ns_device', id); } catch {}
    try { document.cookie = `ns_device=${id}; max-age=63072000; path=/; SameSite=Lax; Secure`; } catch {}
    return id;
  }
  let cache = null;
  window.NSDevice = {
    get() { if (!cache) { try { cache = { id: deviceId(), fp: fingerprint() }; } catch { cache = { id: '', fp: '' }; } } return cache; },
    header() { const d = this.get(); return d.id ? `${d.id}.${d.fp}` : ''; },
  };
})();
