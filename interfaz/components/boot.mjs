if (['/visita/', '/visita', '/recorrido/', '/recorrido'].includes(window.location.pathname)) {
  await import('./visitor-demo.mjs?v=20261110-visitor-db-words');
} else {
  await import('../app.mjs?v=20261111-registro-correo');
}
