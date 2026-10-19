// Tavi v1 only: strict host RPC for close, no Social or game tokens.
const button = document.getElementById('returnTavi');
let seq = 0;
button?.addEventListener('click', () => {
  const id = ++seq;
  window.parent.postMessage({channel:'tavi.extension/v1',direction:'request',id,method:'ui.close'}, '*');
  button.disabled = true;
  setTimeout(() => {button.disabled=false;}, 1500);
});
