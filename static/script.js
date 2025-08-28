const toggle = document.getElementById('theme-toggle');
function applyTheme(t){
  if(t === 'dark') document.documentElement.setAttribute('data-theme','dark');
  else document.documentElement.removeAttribute('data-theme');
}
const stored = localStorage.getItem('theme') || 'light';
applyTheme(stored);
if(toggle){
  toggle.addEventListener('click', ()=>{
    const now = (localStorage.getItem('theme')||'light') === 'light' ? 'dark' : 'light';
    localStorage.setItem('theme', now);
    applyTheme(now);
  });
}

async function fetchPrice(ticker, el){
  try{
    const r = await fetch(`/api/price?ticker=${encodeURIComponent(ticker)}`);
    const j = await r.json();
    el.textContent = j.price ?? 'N/A';
  }catch(e){ el.textContent = 'N/A' }
}
