'use strict';

const config = JSON.parse(document.getElementById('configuracion').textContent);
const currency = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 2 });
const number = new Intl.NumberFormat('es-CO');
const dateFormat = new Intl.DateTimeFormat('es-CO', { day: '2-digit', month: 'short', year: 'numeric' });

const resources = {
  destinos: {
    title: 'Destinos', singular: 'destino', gender: 'o', order: '01',
    description: 'Los lugares que forman parte de cada experiencia.',
    placeholder: 'Nombre, ciudad o código',
    tip: 'Organiza primero los destinos y después agrúpalos en paquetes.',
    empty: 'Registra el primer destino para empezar a diseñar tus rutas.',
    columns: ['Destino', 'Código', 'Ciudad', 'País', 'Acciones'],
  },
  paquetes: {
    title: 'Paquetes', singular: 'paquete', gender: 'o', order: '02',
    description: 'Rutas, fechas y cupos para tus próximas experiencias.',
    placeholder: 'Nombre o destino',
    tip: 'Los cupos disponibles descuentan las personas con reservas pendientes o confirmadas.',
    empty: 'Crea un paquete, selecciona sus destinos y define las fechas del viaje.',
    columns: ['Paquete', 'Destinos', 'Precio por persona', 'Cupos disponibles', 'Estado', 'Acciones'],
  },
  reservas: {
    title: 'Reservas', singular: 'reserva', gender: 'a', order: '03',
    description: 'Acompaña a cada cliente desde su reserva hasta el viaje.',
    placeholder: 'Cliente, paquete o estado',
    tip: 'Las canceladas liberan cupos. El valor de una reserva no acredita un pago recibido.',
    empty: 'Registra tu primera reserva eligiendo un cliente y un paquete disponible.',
    columns: ['Cliente', 'Paquete', 'Personas', 'Valor de la reserva', 'Estado', 'Acciones'],
  },
};

const state = {
  active: 'destinos', data: { destinos: [], paquetes: [], reservas: [] },
  loaded: false, loading: false, saving: false, dialog: null, updatedAt: null,
};
const elements = {
  title: document.getElementById('page-title'),
  description: document.getElementById('page-description'),
  breadcrumb: document.getElementById('breadcrumb-current'),
  listTitle: document.getElementById('list-title'),
  recordCount: document.getElementById('record-count'),
  create: document.getElementById('create-button'),
  refresh: document.getElementById('refresh-button'),
  search: document.getElementById('search-input'),
  panel: document.getElementById('data-panel'),
  table: document.getElementById('table-container'),
  empty: document.getElementById('empty-state'),
  emptyTitle: document.getElementById('empty-title'),
  emptyDescription: document.getElementById('empty-description'),
  notice: document.getElementById('page-notice'),
  dialog: document.getElementById('record-dialog'),
  form: document.getElementById('record-form'),
  formError: document.getElementById('form-error'),
  save: document.getElementById('save-button'),
};

function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = String(text);
  if (className) element.className = className;
  return element;
}

function formatDate(value) {
  if (!value) return 'Sin fecha';
  const date = new Date(`${value}T12:00:00`);
  return Number.isNaN(date.getTime()) ? String(value) : dateFormat.format(date);
}

function statusLabel(value) {
  return { PENDIENTE: 'Pendiente', CONFIRMADA: 'Confirmada', CANCELADA: 'Cancelada' }[value] || String(value);
}

function showNotice(message, error = false) {
  elements.notice.textContent = message;
  elements.notice.hidden = !message;
  elements.notice.classList.toggle('notice-error', error);
  elements.notice.setAttribute('role', error ? 'alert' : 'status');
}

async function request(path, options = {}) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetch(`${config.apiBaseUrl}${path}`, {
      ...options,
      signal: controller.signal,
      headers: { Accept: 'application/json', ...(options.body ? { 'Content-Type': 'application/json' } : {}) },
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.error || `No se pudo completar la solicitud (HTTP ${response.status}).`);
    }
    return response.status === 204 ? null : await response.json();
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('La API está tardando en responder. Intenta actualizar de nuevo.');
    if (error instanceof TypeError) throw new Error('No se pudo conectar con la API. Comprueba que el servicio esté iniciado.');
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

async function refreshData(successMessage = '') {
  if (state.loading) return;
  state.loading = true;
  elements.refresh.disabled = true;
  elements.refresh.textContent = 'Actualizando...';
  showNotice('');
  render();
  try {
    const entries = await Promise.all(Object.keys(resources).map(async (resource) => {
      const values = await request(`/${resource}`);
      if (!Array.isArray(values)) throw new Error(`La API no devolvió una lista de ${resource}.`);
      return [resource, values];
    }));
    state.data = Object.fromEntries(entries);
    state.loaded = true;
    state.updatedAt = new Date();
    document.getElementById('connection-status').textContent = 'API conectada';
    document.getElementById('connection-dot').className = 'connection-dot online';
    if (successMessage) showNotice(successMessage);
  } catch (error) {
    state.loaded = false;
    document.getElementById('connection-status').textContent = 'API sin conexión';
    document.getElementById('connection-dot').className = 'connection-dot offline';
    showNotice(successMessage ? `${successMessage} No fue posible actualizar la lista: ${error.message}` : error.message, true);
  } finally {
    state.loading = false;
    elements.refresh.disabled = false;
    elements.refresh.textContent = 'Actualizar datos';
    render();
  }
}

function filteredRows() {
  const query = elements.search.value.trim().toLocaleLowerCase('es');
  if (!query) return state.data[state.active];
  return state.data[state.active].filter((item) => {
    const content = state.active === 'destinos'
      ? [item.codigo, item.nombre, item.ciudad, item.pais, item.descripcion]
      : state.active === 'paquetes'
        ? [item.nombre, item.descripcion, ...(item.destinos || []).map((destination) => destination.nombre)]
        : [item.cliente_nombre, item.cliente_email, item.paquete_nombre, statusLabel(item.estado)];
    return content.join(' ').toLocaleLowerCase('es').includes(query);
  });
}

function render() {
  const resource = resources[state.active];
  elements.title.textContent = resource.title;
  elements.breadcrumb.textContent = resource.title;
  elements.description.textContent = resource.description;
  elements.listTitle.textContent = `${resource.title} registrad${resource.gender}s`;
  elements.create.textContent = `Nuev${resource.gender} ${resource.singular}`;
  elements.create.disabled = state.loading || !state.loaded;
  elements.search.placeholder = resource.placeholder;
  elements.search.disabled = state.loading || !state.loaded;
  elements.panel.setAttribute('aria-busy', String(state.loading));
  document.getElementById('section-tip').textContent = resource.tip;
  elements.empty.querySelector('.state-number').textContent = resource.order;
  document.querySelectorAll('[data-resource]').forEach((button) => {
    const active = button.dataset.resource === state.active;
    button.classList.toggle('selected', active);
    if (active) button.setAttribute('aria-current', 'page');
    else button.removeAttribute('aria-current');
  });
  for (const key of Object.keys(resources)) {
    document.getElementById(`count-${key}`).textContent = state.loaded ? number.format(state.data[key].length) : '-';
  }
  document.getElementById('updated-at').textContent = state.loaded && state.updatedAt
    ? `Actualizado a las ${state.updatedAt.toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`
    : 'Información pendiente de actualizar';
  elements.table.replaceChildren();
  if (state.loading || !state.loaded) {
    elements.empty.hidden = false;
    elements.recordCount.textContent = state.loading ? 'Consultando registros' : 'Información no disponible';
    elements.emptyTitle.textContent = state.loading ? `Cargando ${state.active}` : 'No pudimos cargar los registros';
    elements.emptyDescription.textContent = state.loading
      ? 'Estamos consultando la información más reciente.'
      : 'Revisa la conexión y pulsa Actualizar datos para volver a intentarlo.';
    return;
  }
  const rows = filteredRows();
  const total = state.data[state.active].length;
  elements.recordCount.textContent = elements.search.value.trim()
    ? `${number.format(rows.length)} de ${number.format(total)} registros`
    : `${number.format(total)} ${total === 1 ? 'registro' : 'registros'}`;
  elements.empty.hidden = rows.length > 0;
  if (rows.length === 0) {
    elements.emptyTitle.textContent = elements.search.value.trim() ? 'Sin coincidencias' : `Aún no hay ${state.active}`;
    elements.emptyDescription.textContent = elements.search.value.trim() ? 'Prueba otro nombre o borra la búsqueda para ver todos los registros.' : resource.empty;
    return;
  }
  const table = node('table');
  table.append(node('caption', `${resource.title}: ${rows.length} registros`, 'visually-hidden'));
  const head = node('thead');
  const header = node('tr');
  resource.columns.forEach((label, index) => {
    const cell = node('th', label, index === resource.columns.length - 1 ? 'actions-cell' : '');
    cell.scope = 'col';
    header.append(cell);
  });
  head.append(header);
  table.append(head);
  const body = node('tbody');
  for (const item of rows) body.append(renderRow(item));
  table.append(body);
  elements.table.append(table);
}

function primaryCell(title, subtitle) {
  const cell = node('td', title, 'primary-cell');
  if (subtitle) cell.append(node('span', subtitle, 'cell-secondary'));
  return cell;
}

function statusCell(value, label) {
  const cell = node('td');
  cell.append(node('span', label || statusLabel(value), `status-tag ${value.toLowerCase()}`));
  return cell;
}

function renderRow(item) {
  const row = node('tr');
  if (state.active === 'destinos') {
    row.append(primaryCell(item.nombre), node('td', item.codigo), node('td', item.ciudad), node('td', item.pais));
  } else if (state.active === 'paquetes') {
    row.append(
      primaryCell(item.nombre, `${formatDate(item.fecha_inicio)} a ${formatDate(item.fecha_fin)}`),
      node('td', (item.destinos || []).map((destination) => destination.nombre).join(', '), 'destinations-cell'),
      node('td', currency.format(item.precio), 'numeric-cell'),
      node('td', `${number.format(item.cupos_disponibles)} de ${number.format(item.cupo_maximo)}`, 'numeric-cell'),
      statusCell(item.activo ? 'activo' : 'inactivo', item.activo ? 'Activo' : 'Inactivo'),
    );
  } else {
    row.append(
      primaryCell(item.cliente_nombre, item.cliente_email),
      primaryCell(item.paquete_nombre, `Reservado el ${formatDate(item.fecha_reserva)}`),
      node('td', number.format(item.cantidad_personas), 'numeric-cell'),
      node('td', currency.format(item.total), 'numeric-cell'),
      statusCell(item.estado),
    );
  }
  const actions = node('td', undefined, 'actions-cell');
  const edit = node('button', 'Editar', 'row-button');
  edit.type = 'button';
  edit.setAttribute('aria-label', `Editar ${item.nombre || item.cliente_nombre}`);
  edit.addEventListener('click', () => openForm(item));
  const remove = node('button', 'Eliminar', 'row-button danger');
  remove.type = 'button';
  remove.setAttribute('aria-label', `Eliminar ${item.nombre || item.cliente_nombre}`);
  remove.addEventListener('click', () => removeItem(item));
  actions.append(edit, remove);
  row.append(actions);
  return row;
}

function openForm(item = null) {
  if (!state.loaded || state.loading || state.saving) return;
  const resource = resources[state.active];
  if (state.active === 'paquetes' && state.data.destinos.length === 0) {
    showNotice('Primero registra al menos un destino para poder crear un paquete.', true);
    return;
  }
  if (state.active === 'reservas' && state.data.paquetes.length === 0) {
    showNotice('Primero crea un paquete turístico para poder registrar una reserva.', true);
    return;
  }
  state.dialog = { resource: state.active, item };
  elements.form.reset();
  elements.formError.hidden = true;
  document.getElementById('dialog-title').textContent = `${item ? 'Editar' : 'Crear'} ${resource.singular}`;
  document.getElementById('dialog-eyebrow').textContent = item ? 'ACTUALIZAR REGISTRO' : 'NUEVO REGISTRO';
  elements.save.textContent = item ? 'Guardar cambios' : `Crear ${resource.singular}`;
  document.querySelectorAll('[data-fields]').forEach((group) => {
    group.hidden = group.dataset.fields !== state.active;
    group.disabled = group.hidden;
  });
  const group = elements.form.querySelector(`[data-fields="${state.active}"]`);
  if (state.active === 'paquetes') renderDestinationOptions(item);
  if (state.active === 'reservas') renderPackageOptions();
  if (item) {
    group.querySelectorAll('input:not([type="checkbox"]), select, textarea').forEach((field) => {
      if (item[field.name] !== undefined && item[field.name] !== null) field.value = String(item[field.name]);
    });
  }
  if (state.active === 'reservas') updatePackageDetail();
  elements.dialog.showModal();
  group.querySelector('input, select, textarea')?.focus();
}

function renderDestinationOptions(item) {
  const selected = new Set(item?.destino_ids || (item?.destinos || []).map((destination) => destination.id));
  const container = document.getElementById('destination-options');
  container.replaceChildren();
  state.data.destinos.forEach((destination) => {
    const label = node('label', undefined, 'destination-option');
    const input = node('input');
    input.type = 'checkbox';
    input.name = 'destino_ids';
    input.value = String(destination.id);
    input.checked = selected.has(destination.id);
    const text = node('span', destination.nombre);
    text.append(node('small', `${destination.ciudad}, ${destination.pais}`));
    label.append(input, text);
    container.append(label);
  });
}

function renderPackageOptions() {
  const select = document.getElementById('reserva-paquete');
  select.replaceChildren();
  const placeholder = node('option', 'Selecciona un paquete');
  placeholder.value = '';
  select.append(placeholder);
  for (const item of state.data.paquetes) {
    const option = node('option', `${item.nombre} | ${currency.format(item.precio)} | ${item.cupos_disponibles} cupos${item.activo ? '' : ' | Inactivo'}`);
    option.value = String(item.id);
    select.append(option);
  }
}

function updatePackageDetail() {
  const id = Number(document.getElementById('reserva-paquete').value);
  const detail = document.getElementById('package-detail');
  const selected = state.data.paquetes.find((item) => item.id === id);
  if (!selected) {
    detail.textContent = 'Selecciona un paquete para consultar precio y disponibilidad.';
    return;
  }
  const previous = state.dialog?.item;
  const ownPlaces = previous && previous.paquete_id === id && previous.estado !== 'CANCELADA' ? previous.cantidad_personas : 0;
  const available = Number(selected.cupos_disponibles) + Number(ownPlaces);
  const people = Number(document.getElementById('reserva-personas').value);
  const cancelled = document.getElementById('reserva-estado').value === 'CANCELADA';
  const keepPreviousTotal = previous && previous.paquete_id === id && previous.cantidad_personas === people;
  const total = keepPreviousTotal
    ? currency.format(previous.total)
    : Number.isFinite(people) && people > 0 ? currency.format(selected.precio * people) : 'Sin calcular';
  const totalLabel = keepPreviousTotal ? 'Valor conservado de la reserva' : 'Valor estimado';
  detail.textContent = `${formatDate(selected.fecha_inicio)} a ${formatDate(selected.fecha_fin)}. Precio actual: ${currency.format(selected.precio)} por persona. ${available} cupos disponibles${ownPlaces ? ', incluidos los de esta reserva' : ''}. ${totalLabel}: ${total}.${cancelled ? ' La reserva cancelada no ocupará cupos.' : ''}${selected.activo ? '' : ' Este paquete está inactivo.'}`;
}

function showFormError(message) {
  elements.formError.textContent = message;
  elements.formError.hidden = false;
  elements.formError.focus();
}

function formPayload() {
  const values = new FormData(elements.form);
  const text = (key) => String(values.get(key) || '').trim();
  const numeric = (key) => Number(values.get(key));
  if (state.dialog.resource === 'destinos') {
    return { codigo: text('codigo'), nombre: text('nombre'), pais: text('pais'), ciudad: text('ciudad'), descripcion: text('descripcion') };
  }
  if (state.dialog.resource === 'paquetes') {
    const destinations = values.getAll('destino_ids').map(Number);
    if (destinations.length === 0) throw new Error('Selecciona al menos un destino para este paquete.');
    if (text('fecha_fin') < text('fecha_inicio')) throw new Error('La fecha de fin no puede ser anterior a la fecha de inicio.');
    return {
      nombre: text('nombre'), descripcion: text('descripcion'), precio: numeric('precio'),
      duracion_dias: numeric('duracion_dias'), fecha_inicio: text('fecha_inicio'), fecha_fin: text('fecha_fin'),
      cupo_maximo: numeric('cupo_maximo'), activo: text('activo') === 'true', destino_ids: destinations,
    };
  }
  return {
    cliente_nombre: text('cliente_nombre'), cliente_email: text('cliente_email'),
    cantidad_personas: numeric('cantidad_personas'), paquete_id: numeric('paquete_id'), estado: text('estado'),
  };
}

function setSaving(saving) {
  state.saving = saving;
  elements.save.disabled = saving;
  document.getElementById('cancel-dialog').disabled = saving;
  document.getElementById('close-dialog').disabled = saving;
  elements.form.setAttribute('aria-busy', String(saving));
}

async function saveRecord(event) {
  event.preventDefault();
  if (state.saving || !state.dialog) return;
  elements.formError.hidden = true;
  const { resource, item } = state.dialog;
  const originalLabel = elements.save.textContent;
  try {
    const payload = formPayload();
    setSaving(true);
    elements.save.textContent = 'Guardando...';
    await request(`/${resource}${item ? `/${item.id}` : ''}`, {
      method: item ? 'PUT' : 'POST', body: JSON.stringify(payload),
    });
    elements.dialog.close();
    const { singular, gender } = resources[resource];
    await refreshData(`${singular.charAt(0).toUpperCase() + singular.slice(1)} ${item ? 'actualizad' : 'registrad'}${gender} correctamente.`);
  } catch (error) {
    showFormError(error.message);
  } finally {
    setSaving(false);
    elements.save.textContent = originalLabel;
  }
}

async function removeItem(item) {
  if (state.saving || state.loading || !state.loaded) return;
  const resource = state.active;
  const singular = resources[resource].singular;
  if (!window.confirm(`¿Eliminar ${singular} "${item.nombre || item.cliente_nombre}"? Esta acción no se puede deshacer.`)) return;
  state.saving = true;
  elements.table.querySelectorAll('button').forEach((button) => { button.disabled = true; });
  elements.create.disabled = true;
  elements.refresh.disabled = true;
  try {
    await request(`/${resource}/${item.id}`, { method: 'DELETE' });
    await refreshData('Registro eliminado correctamente.');
  } catch (error) {
    showNotice(error.message, true);
  } finally {
    state.saving = false;
    elements.refresh.disabled = false;
    render();
  }
}

document.querySelectorAll('[data-resource]').forEach((button) => {
  button.addEventListener('click', () => {
    state.active = button.dataset.resource;
    elements.search.value = '';
    render();
  });
});
elements.search.addEventListener('input', render);
elements.refresh.addEventListener('click', () => refreshData());
elements.create.addEventListener('click', () => openForm());
elements.form.addEventListener('submit', saveRecord);
document.getElementById('cancel-dialog').addEventListener('click', () => elements.dialog.close());
document.getElementById('close-dialog').addEventListener('click', () => elements.dialog.close());
elements.dialog.addEventListener('cancel', (event) => { if (state.saving) event.preventDefault(); });
elements.dialog.addEventListener('close', () => { state.dialog = null; });
['reserva-paquete', 'reserva-personas', 'reserva-estado'].forEach((id) => {
  document.getElementById(id).addEventListener('input', updatePackageDetail);
});
refreshData();
