export async function renderDocumentPage({ kind, business, state, api, notice, escapeHtml, formatMoney, todayInDhaka }) {
  const isSale = kind === 'sales';
  const h = escapeHtml;
  const [documents, products, contacts] = await Promise.all([
    api(`/api/businesses/${business.id}/${kind}/`),
    api(`/api/businesses/${business.id}/products/`),
    api(`/api/businesses/${business.id}/contacts/`),
  ]);
  state.products = products;
  state.contacts = contacts;

  const contactRole = isSale ? 'is_customer' : 'is_supplier';
  const contactsForDocument = contacts.filter(contact => contact[contactRole]);
  const productOptions = products.map(product => `<option value="${h(product.id)}">${h(product.name)} · ${h(product.sku)}</option>`).join('');
  const contactOptions = contactsForDocument.map(contact => `<option value="${h(contact.id)}">${h(contact.display_name)}</option>`).join('');
  const locationOptions = state.locations.map(location => `<option value="${h(location.id)}">${h(location.name)}</option>`).join('');
  const documentNumber = `${isSale ? 'S' : 'P'}-${todayInDhaka().replaceAll('-', '')}-${String(Date.now()).slice(-5)}`;
  const tableRows = documents.map(document => {
    const contactId = isSale ? document.customer : document.supplier;
    const contact = contacts.find(item => String(item.id) === String(contactId));
    const location = state.locations.find(item => String(item.id) === String(document.location));
    const number = isSale ? document.sale_number : document.purchase_number;
    const date = isSale ? document.sale_date : document.purchase_date;
    const action = document.status === 'DRAFT'
      ? `<button class="button secondary mini" data-post-id="${h(document.id)}">${isSale ? 'Post sale' : 'Receive stock'}</button>`
      : '—';
    return `<tr><td><b>${h(number)}</b></td><td>${h(contact?.display_name || (isSale ? 'Walk-in' : 'Supplier'))}</td><td>${h(location?.name || '—')}</td><td>${h(date)}</td><td>${formatMoney(document.grand_total, business.currency_code)}</td><td><span class="status">${h(document.status)}</span></td><td>${action}</td></tr>`;
  }).join('');

  document.querySelector('#page-content').innerHTML = `
    <div class="page-heading"><div><h2>${isSale ? 'Sales invoices' : 'Purchase orders'}</h2><p>${isSale ? 'Build an itemized invoice, collect payment, and update stock.' : 'Record supplier stock, payments, and outstanding balance.'}</p></div></div>
    <section class="form-card document-editor">
      <div class="editor-title"><div><h2>${isSale ? 'New sale' : 'New purchase'}</h2><p>Document <b>${h(documentNumber)}</b></p></div><span class="status">${isSale ? 'SALES' : 'PURCHASE'}</span></div>
      <form id="document-form">
        <div class="document-meta">
          <label>${isSale ? 'Customer' : 'Supplier'}<select name="contact_id" ${isSale ? '' : 'required'}><option value="">${isSale ? 'Walk-in customer' : 'Choose supplier'}</option>${contactOptions}</select></label>
          <label>${isSale ? 'Sell from' : 'Receive at'}<select name="location" required>${locationOptions}</select></label>
          <label>Document date<input name="document_date" type="date" value="${todayInDhaka()}" required></label>
        </div>
        <div class="line-items-head"><h3>Items</h3><button type="button" class="button secondary mini" id="add-line">＋ Add item</button></div>
        <div class="table-wrap"><table class="invoice-table"><thead><tr><th>Product</th><th>Quantity</th><th>${isSale ? 'Unit price' : 'Unit cost'}</th><th>Line total</th><th></th></tr></thead><tbody id="invoice-lines"></tbody></table></div>
        <div class="document-footer">
          <div class="payment-fields">
            <label>${isSale ? 'Collected now' : 'Paid to supplier now'}<div class="money-input"><span>৳</span><input name="payment_amount" type="number" min="0" step="0.01" value="0"></div></label>
            <label>Payment method<select name="payment_method"><option value="CASH">Cash</option><option value="BANK">Bank</option><option value="MFS">Mobile payment</option><option value="OTHER">Other</option></select></label>
          </div>
          <div class="document-total"><span>Total</span><strong id="invoice-total">${formatMoney(0, business.currency_code)}</strong><small>${isSale ? 'Unpaid amount stays as customer due.' : 'Unpaid amount stays as supplier payable.'}</small></div>
        </div>
        <div class="form-actions"><button class="button secondary" type="submit" name="intent" value="draft">Save draft</button><button class="button primary" type="submit" name="intent" value="post">${isSale ? 'Complete sale' : 'Receive stock'}</button></div>
      </form>
    </section>
    <section class="panel"><div class="panel-heading"><h2>${isSale ? 'Sales history' : 'Purchase history'}</h2><span>${documents.length} documents</span></div>
      <div class="table-wrap"><table><thead><tr>${['Number', isSale ? 'Customer' : 'Supplier', 'Location', 'Date', 'Total', 'Status', 'Action'].map(label => `<th>${label}</th>`).join('')}</tr></thead><tbody>${tableRows || `<tr><td colspan="7" class="empty">No documents yet</td></tr>`}</tbody></table></div>
    </section>`;

  const lineBody = document.querySelector('#invoice-lines');
  const recalculate = () => {
    let total = 0;
    lineBody.querySelectorAll('.invoice-line').forEach(row => {
      const quantity = Number(row.querySelector('[name="quantity"]').value || 0);
      const price = Number(row.querySelector('[name="unit_price"]').value || 0);
      const lineTotal = quantity * price;
      total += lineTotal;
      row.querySelector('.line-total').textContent = formatMoney(lineTotal, business.currency_code);
    });
    document.querySelector('#invoice-total').textContent = formatMoney(total, business.currency_code);
  };
  const addLine = () => {
    const row = document.createElement('tr');
    row.className = 'invoice-line';
    row.innerHTML = `<td><select name="product" required><option value="">Choose product</option>${productOptions}</select></td><td><input name="quantity" type="number" min="0.001" step="0.001" value="1" required></td><td><input name="unit_price" type="number" min="0" step="0.01" value="0" required></td><td class="line-total">${formatMoney(0, business.currency_code)}</td><td><button type="button" class="remove-line" aria-label="Remove item">×</button></td>`;
    lineBody.append(row);
    row.querySelector('[name="product"]').addEventListener('change', event => {
      const product = products.find(item => item.id === event.target.value);
      row.querySelector('[name="unit_price"]').value = product ? (isSale ? product.selling_price : product.purchase_price) : 0;
      recalculate();
    });
    row.querySelectorAll('input').forEach(input => input.addEventListener('input', recalculate));
    row.querySelector('.remove-line').addEventListener('click', () => {
      if (lineBody.querySelectorAll('.invoice-line').length > 1) row.remove();
      recalculate();
    });
    recalculate();
  };
  addLine();
  document.querySelector('#add-line').addEventListener('click', addLine);
  document.querySelector('#document-form').addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const values = Object.fromEntries(new FormData(form));
    const items = [...lineBody.querySelectorAll('.invoice-line')].map(row => ({
      product: row.querySelector('[name="product"]').value,
      quantity: Number(row.querySelector('[name="quantity"]').value),
      [isSale ? 'unit_price' : 'unit_cost']: Number(row.querySelector('[name="unit_price"]').value),
    }));
    const payload = {
      [isSale ? 'sale_number' : 'purchase_number']: documentNumber,
      [isSale ? 'sale_date' : 'purchase_date']: values.document_date,
      location: values.location,
      [isSale ? 'customer' : 'supplier']: values.contact_id || null,
      items,
    };
    if (isSale && !payload.customer) delete payload.customer;
    try {
      const created = await api(`/api/businesses/${business.id}/${kind}/`, { method: 'POST', body: JSON.stringify(payload) });
      if (event.submitter?.value === 'post') {
        await api(`/api/businesses/${business.id}/${kind}/${created.id}/${isSale ? 'complete' : 'receive'}/`, {
          method: 'POST',
          body: JSON.stringify({ payment_amount: Number(values.payment_amount || 0), payment_method: values.payment_method }),
        });
        notice(isSale ? 'Sale posted. Stock and customer balance are updated.' : 'Purchase received. Stock and supplier balance are updated.');
      } else notice(`${isSale ? 'Sale' : 'Purchase'} draft saved.`);
      await renderDocumentPage({ kind, business, state, api, notice, escapeHtml, formatMoney, todayInDhaka });
    } catch (error) { notice(error.message, true); }
  });

  document.querySelectorAll('[data-post-id]').forEach(button => button.addEventListener('click', async () => {
    try {
      await api(`/api/businesses/${business.id}/${kind}/${button.dataset.postId}/${isSale ? 'complete' : 'receive'}/`, { method: 'POST', body: JSON.stringify({}) });
      notice(isSale ? 'Sale posted and stock updated.' : 'Purchase received and stock updated.');
      await renderDocumentPage({ kind, business, state, api, notice, escapeHtml, formatMoney, todayInDhaka });
    } catch (error) { notice(error.message, true); }
  }));
}
