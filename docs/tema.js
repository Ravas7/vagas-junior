/* Roda no <head>, antes de desenhar: aplica o tema escolhido (sem piscar).
 * Em arquivo próprio (e não escrito no HTML) por causa da política de segurança (CSP). */
try {
  const t = localStorage.getItem("vagas-junior:tema:v1");
  if (t === "light" || t === "dark") document.documentElement.dataset.theme = t;
} catch (e) { /* modo privado */ }
// no painel, fica escondido até confirmar o login (login.js tira esta classe)
if (document.currentScript && document.currentScript.dataset.gated !== undefined) document.documentElement.classList.add("gated");
