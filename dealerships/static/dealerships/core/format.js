export function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char]));
}

export function formatMoney(value, currency = 'BDT') {
  return new Intl.NumberFormat('en-BD', {
    style: 'currency', currency, maximumFractionDigits: 2,
  }).format(Number(value || 0));
}

export function todayInDhaka() {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Dhaka', year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(new Date());
}
