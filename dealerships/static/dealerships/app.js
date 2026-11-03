import { renderDocumentPage } from './pages/documents.js';
import { request } from './core/api.js';
import { escapeHtml as esc, formatMoney, todayInDhaka } from './core/format.js';

(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const tokenKey = 'dealership_desk_token';
  const state = { token: localStorage.getItem(tokenKey), business: null, user: null, locations: [], products: [], contacts: [], page: 'overview' };
  const authView = $('#auth-view');
  const appView = $('#app-view');
  let isSignup = false;

  async function api(path, options = {}) {
    try { return await request(path, { ...options, token: state.token }); }
    catch (error) {
      if (error.status === 401 && state.token) { localStorage.removeItem(tokenKey); state.token = null; showAuth(); }
      throw error;
    }
  }

  function notice(message, isError = false) {
    const box = $('#notice');
    box.textContent = message;
    box.classList.toggle('error', isError);
    box.classList.remove('hidden');
    window.clearTimeout(notice.timer);
    notice.timer = window.setTimeout(() => box.classList.add('hidden'), 4500);
  }

  function showAuth() {
    authView.classList.remove('hidden'); appView.classList.add('hidden');
  }

  function renderAuthMode() {
    $('#signup-fields').classList.toggle('hidden', !isSignup);
    $('#login-fields').classList.toggle('hidden', isSignup);
    $$('#signup-fields input').forEach(input => { input.disabled = !isSignup; });
    $$('#login-fields input').forEach(input => { input.disabled = isSignup; });
    $('#auth-title').textContent = isSignup ? 'Create your workspace' : 'Sign in';
    $('#auth-eyebrow').textContent = isSignup ? 'GET STARTED' : 'WELCOME BACK';
    $('#auth-description').textContent = isSignup ? 'Set up your dealership in a few minutes.' : 'Enter your account details to continue.';
    $('#auth-submit').textContent = isSignup ? 'Create dealership' : 'Sign in';
    $('#switch-copy').textContent = isSignup ? 'Already have an account?' : 'New to Dealership Desk?';
    $('#auth-switch').textContent = isSignup ? 'Sign in' : 'Create an account';
  }

  async function loadWorkspace() {
    const businesses = await api('/api/me/businesses/');
    if (!businesses.length) throw new Error('Your account is not connected to a dealership yet.');
    state.business = businesses[0];
    state.locations = businesses[0].locations || [];
    const me = await api('/api/auth/me/');
    state.user = me;
    $('#business-name').textContent = state.business.name;
    $('#business-location').textContent = state.locations.find(location => location.is_default)?.name || state.locations[0]?.name || 'No location';
    $('#user-name').textContent = me.username;
    $('#user-avatar').textContent = me.username.slice(0, 1).toUpperCase();
    $('#today-label').textContent = new Intl.DateTimeFormat('en', { dateStyle: 'medium' }).format(new Date());
    authView.classList.add('hidden'); appView.classList.remove('hidden');
    await navigate(state.page);
  }

  function businessPath(resource) { return `/api/businesses/${encodeURIComponent(state.business.id)}/${resource}/`; }
  function emptyRow(columns, message = 'Nothing here yet') { return `<tr><td colspan="${columns}" class="empty">${esc(message)}</td></tr>`; }
  function table(headers, rows) {
    return `<div class="table-wrap"><table><thead><tr>${headers.map(h => `<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows || emptyRow(headers.length)}</tbody></table></div>`;
  }
  function locationOptions() { return state.locations.map(item => `<option value="${esc(item.id)}">${esc(item.name)}</option>`).join(''); }
  function contactOptions(type) { return state.contacts.filter(item => type === 'customer' ? item.is_customer : item.is_supplier).map(item => `<option value="${esc(item.id)}">${esc(item.display_name)}</option>`).join(''); }
  async function loadShared() {
    [state.products, state.contacts] = await Promise.all([api(businessPath('products')), api(businessPath('contacts'))]);
  }

  async function navigate(page) {
    state.page = page;
    $$('.nav-item').forEach(button => button.classList.toggle('active', button.dataset.page === page));
    const title = { overview: 'Overview', products: 'Products & stock', sales: 'Sales', purchases: 'Purchases', contacts: 'Customers & suppliers' }[page] || 'Overview';
    $('#page-title').textContent = title;
    $('#page-kicker').textContent = state.business.name.toUpperCase();
    $('#page-content').innerHTML = '<div class="panel empty">Loading your business data...</div>';
    try {
      await loadShared();
      if (page === 'overview') await renderOverview();
      else if (page === 'products') await renderProducts();
      else if (page === 'sales') await renderDocuments('sales');
      else if (page === 'purchases') await renderDocuments('purchases');
      else if (page === 'contacts') await renderContacts();
    } catch (error) { notice(error.message, true); $('#page-content').innerHTML = '<section class="panel empty">Could not load this page. Please try again.</section>'; }
  }

  async function renderOverview() {
    const [summary, sales] = await Promise.all([api(`/api/businesses/${state.business.id}/summary/`), api(businessPath('sales'))]);
    const stockCount = new Set(summary.stock.map(row => row.product_id)).size;
    const recent = sales.slice(0, 5).map(sale => {
      const customer = state.contacts.find(item => String(item.id) === String(sale.customer));
      return `<tr><td><b>${esc(sale.sale_number)}</b></td><td>${esc(customer?.display_name || 'Walk-in')}</td><td>${esc(sale.sale_date)}</td><td>${formatMoney(sale.grand_total)}</td><td><span class="status">${esc(sale.status)}</span></td></tr>`;
    }).join('');
    const stockRows = summary.stock.slice(0, 5).map(item => `<tr><td><b>${esc(item.product__name)}</b><br><span class="muted">${esc(item.product__sku)}</span></td><td>${esc(item.location__name)}</td><td>${esc(item.quantity)}</td></tr>`).join('');
    $('#page-content').innerHTML = `<div class="metrics">
      <article class="metric"><div class="metric-label">Sales</div><div class="metric-value">${formatMoney(summary.sales_total)}</div><div class="metric-note">${summary.sales_count} completed invoices</div></article>
      <article class="metric"><div class="metric-label">Customer dues</div><div class="metric-value">${formatMoney(summary.customer_due_total)}</div><div class="metric-note">Outstanding receivables</div></article>
      <article class="metric"><div class="metric-label">SKUs in stock</div><div class="metric-value">${esc(stockCount)}</div><div class="metric-note">Across ${state.locations.length} locations</div></article>
      <article class="metric"><div class="metric-label">Supplier dues</div><div class="metric-value">${formatMoney(summary.supplier_due_total)}</div><div class="metric-note">Outstanding payables</div></article>
    </div><div class="content-grid"><section class="panel"><div class="panel-heading"><h2>Recent sales</h2><span>${summary.sales_count} total</span></div>${table(['Invoice', 'Customer', 'Date', 'Amount', 'Status'], recent)}</section><section class="panel"><div class="panel-heading"><h2>Stock on hand</h2><span>${summary.stock.length} records</span></div>${table(['Product', 'Location', 'Quantity'], stockRows)}</section></div>`;
  }

  async function renderProducts() {
    const [products, stock] = await Promise.all([api(businessPath('products')), api(`${businessPath('products')}stock/`)]);
    state.products = products;
    const stockByProduct = new Map(); stock.forEach(row => stockByProduct.set(row.product_id, (stockByProduct.get(row.product_id) || 0) + Number(row.quantity)));
    const rows = products.map(product => `<tr><td><b>${esc(product.name)}</b></td><td>${esc(product.sku)}</td><td>${esc(product.category || '—')}</td><td>${esc(product.unit_name)}</td><td>${formatMoney(product.selling_price)}</td><td>${esc(stockByProduct.get(product.id) || 0)}</td><td><span class="status">${product.is_active ? 'Active' : 'Archived'}</span></td></tr>`).join('');
    $('#page-content').innerHTML = `<div class="page-heading"><div><h2>Product catalog</h2><p>Manage the items your dealership buys and sells.</p></div></div><section class="form-card"><h2>Add a product</h2><form id="product-form" class="inline-form"><label>Product name<input name="name" required maxlength="200"></label><label>SKU / code<input name="sku" required maxlength="64"></label><label>Unit<input name="unit_name" value="piece" required></label><label>Selling price<input name="selling_price" type="number" min="0" step="0.01" value="0" required></label><label>Purchase cost<input name="purchase_price" type="number" min="0" step="0.01" value="0" required></label><button class="button primary" type="submit">Add product</button></form></section><section class="panel"><div class="panel-heading"><h2>All products</h2><span>${products.length} products</span></div>${table(['Product', 'SKU', 'Category', 'Unit', 'Price', 'Stock', 'Status'], rows)}</section>`;
    $('#product-form').addEventListener('submit', async event => {
      event.preventDefault(); const data = Object.fromEntries(new FormData(event.currentTarget));
      data.selling_price = Number(data.selling_price); data.purchase_price = Number(data.purchase_price);
      try { await api(businessPath('products'), { method: 'POST', body: JSON.stringify(data) }); notice('Product added.'); await renderProducts(); }
      catch (error) { notice(error.message, true); }
    });
  }

  async function renderDocuments(kind) {
    await renderDocumentPage({ kind, business: state.business, state, api, notice, escapeHtml: esc, formatMoney, todayInDhaka });
  }

  async function renderContacts() {
    const contacts = await api(businessPath('contacts')); state.contacts = contacts;
    const rows = contacts.map(contact => `<tr><td><b>${esc(contact.display_name)}</b></td><td>${esc(contact.phone || '—')}</td><td>${esc(contact.email || '—')}</td><td>${contact.is_customer ? '<span class="status">Customer</span> ' : ''}${contact.is_supplier ? '<span class="status">Supplier</span>' : ''}</td><td>${esc(contact.is_active ? 'Active' : 'Archived')}</td></tr>`).join('');
    $('#page-content').innerHTML = `<div class="page-heading"><div><h2>Business contacts</h2><p>A contact can be a customer, a supplier, or both.</p></div></div><section class="form-card"><h2>Add a contact</h2><form id="contact-form" class="inline-form"><label>Name<input name="display_name" required maxlength="200"></label><label>Phone<input name="phone" maxlength="32"></label><label>Email<input name="email" type="email"></label><label>Contact type<select name="type"><option value="customer">Customer</option><option value="supplier">Supplier</option><option value="both">Both</option></select></label><button class="button primary" type="submit">Add contact</button></form></section><section class="panel"><div class="panel-heading"><h2>Customers & suppliers</h2><span>${contacts.length} contacts</span></div>${table(['Name', 'Phone', 'Email', 'Type', 'Status'], rows)}</section>`;
    $('#contact-form').addEventListener('submit', async event => {
      event.preventDefault(); const data = Object.fromEntries(new FormData(event.currentTarget));
      data.is_customer = data.type !== 'supplier'; data.is_supplier = data.type !== 'customer'; delete data.type;
      try { await api(businessPath('contacts'), { method: 'POST', body: JSON.stringify(data) }); notice('Contact added.'); await renderContacts(); }
      catch (error) { notice(error.message, true); }
    });
  }

  $('#auth-switch').addEventListener('click', () => { isSignup = !isSignup; $('#auth-error').textContent = ''; renderAuthMode(); });
  $('#auth-form').addEventListener('submit', async event => {
    event.preventDefault(); $('#auth-error').textContent = '';
    const values = Object.fromEntries(new FormData(event.currentTarget));
    const endpoint = isSignup ? '/api/auth/signup/' : '/api/auth/login/';
    const payload = isSignup
      ? { username: values.username, email: values.email, password: values.password, business_name: values.business_name }
      : { username: values.login_username, password: values.login_password };
    try {
      const result = await api(endpoint, { method: 'POST', body: JSON.stringify(payload) });
      state.token = result.token; localStorage.setItem(tokenKey, result.token); state.page = 'overview';
      await loadWorkspace();
    } catch (error) { $('#auth-error').textContent = error.message; }
  });
  $$('.nav-item').forEach(button => button.addEventListener('click', () => navigate(button.dataset.page)));
  $('#quick-sale').addEventListener('click', () => navigate('sales'));
  $('#logout-button').addEventListener('click', async () => {
    try { await api('/api/auth/logout/', { method: 'POST', body: '{}' }); } catch (_) { /* clear the local session even if the server cannot be reached */ }
    localStorage.removeItem(tokenKey); state.token = null; showAuth();
  });

  renderAuthMode();
  if (state.token) loadWorkspace().catch(error => { localStorage.removeItem(tokenKey); state.token = null; showAuth(); $('#auth-error').textContent = error.message; });
})();
