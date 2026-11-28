/* Painel instalável: abre rápido e funciona sem internet com a última lista (sw.js).
 * "Instalar o app" no menu da conta só aparece quando o navegador oferece (Android/Chrome, Edge). */
(() => {
  if ("serviceWorker" in navigator && location.protocol === "https:") addEventListener("load", () => navigator.serviceWorker.register("sw.js"));
  let pedido = null;
  const item = document.getElementById("acct-instalar");
  if (!item) return;
  addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); pedido = e; item.hidden = false; });
  addEventListener("appinstalled", () => { pedido = null; item.hidden = true; });
  item.addEventListener("click", async () => {
    if (!pedido) return;
    pedido.prompt();
    await pedido.userChoice;
    pedido = null; item.hidden = true;
  });
})();
