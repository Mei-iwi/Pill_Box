const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? '—').replace(/[&<>"']/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[char]));

const labels = {
  REMINDING: 'Đang nhắc', ALERT: 'Đang cảnh báo', IDLE: 'Đang chờ',
  PENDING: 'Đang nhắc', ON_TIME: 'Đã lấy đúng giờ', LATE: 'Đã lấy trễ',
  MISSED: 'Chưa ghi nhận lấy', REMINDER_STARTED: 'Bắt đầu nhắc thuốc',
  TAKEN_ON_TIME: 'Xác nhận lấy đúng giờ', TAKEN_LATE: 'Xác nhận lấy trễ',
  WRONG_SLOT: 'Mở sai ngăn', UNSCHEDULED_OPEN: 'Mở ngăn ngoài lịch',
  AMBIGUOUS_OPEN: 'Cần xác định lịch', STORAGE_WARNING: 'Vượt ngưỡng',
  STORAGE_NORMAL: 'Đã về ngưỡng', SENSOR_ERROR: 'Lỗi cảm biến',
  VERIFIED: 'Mã thuốc phù hợp', CONFIRMED: 'Đã xác nhận nạp',
  MEDICATION_MISMATCH: 'Mã thuốc không khớp với ngăn đã chọn.',
  PATIENT_BOX_MISMATCH: 'Người dùng không khớp với hộp thuốc.',
  UNKNOWN_BOX_OR_SLOT: 'Không tìm thấy hộp hoặc ngăn thuốc.',
  ACTOR_MISMATCH: 'Tài khoản xác nhận không khớp.',
  VERIFICATION_EXPIRED: 'Xác minh đã hết hạn. Vui lòng xác minh lại.',
  VERIFICATION_REPLAY: 'Xác minh này đã được sử dụng. Vui lòng xác minh lại.',
  STALE_VERIFICATION: 'Thông tin ngăn đã thay đổi. Vui lòng xác minh lại.',
  APPLIED: 'Đã áp dụng', REJECTED: 'Đã từ chối', INVALID_ACK: 'Phản hồi không hợp lệ',
  PUBLISH_FAILED: 'Gửi không thành công',
  TIMEOUT: 'Hết thời gian chờ ACK',
  REQUEST_STATUS: 'Đọc trạng thái', CLEAR_ALERT: 'Tắt âm & đèn nhắc',
  UPDATE_SCHEDULE: 'Cập nhật lịch'
};
Object.assign(labels, {REFILL_OPEN:'Mở ngăn nạp thuốc', BEGIN_REFILL:'Bắt đầu phiên nạp', END_REFILL:'Kết thúc phiên nạp',
  REFILL_OPEN_REQUIRED:'Chưa ghi nhận mở đúng ngăn trong phiên nạp.', VERIFICATION_REQUIRED:'Vui lòng xác minh mã trước.',
  OPEN:'Cần xử lý', ACKNOWLEDGED:'Đã tiếp nhận', RESOLVED:'Đã xử lý'});
const roleLabels = { family: 'Gia đình', nurse: 'Người chăm sóc', admin: 'Quản trị' };
const views = ['overview', 'schedules', 'history', 'refill', 'devices'];
let token = '', verification = null, verificationContext = '', expiresAt = 0;
let loading = false, refreshQueued = false, caregiver = true, authPrompted = false;
let currentView = 'overview', knownDevices = [], currentSlots = [], lastCommandId = null;
let bootstrapReady = false, accessBlocked = false;
let loginInProgress = false, authVersion = 0;
let refillSessionId = null;
let historyKey = '', historyFetchedAt = 0, historyLoading = false;
const renderCache = new Map();
function renderChanged(name, value, render) {
  const fingerprint = JSON.stringify(value);
  if (renderCache.get(name) === fingerprint) return;
  render(); renderCache.set(name, fingerprint);
}
const listPages = { events: 1, occurrences: 1, audit: 1, commands: 1, alerts: 1 };
const pageSize = 8;

function selected() { return $('#device').value; }
function tone(value) {
  if (['ON_TIME', 'LATE', 'TAKEN_ON_TIME', 'TAKEN_LATE', 'CONFIRMED', 'VERIFIED', 'APPLIED', 'STORAGE_NORMAL'].includes(value)) return 'success';
  if (['MISSED', 'WRONG_SLOT', 'STORAGE_WARNING', 'AMBIGUOUS_OPEN', 'PENDING'].includes(value)) return 'warning';
  if (['SENSOR_ERROR', 'MEDICATION_MISMATCH', 'PATIENT_BOX_MISMATCH', 'REJECTED', 'PUBLISH_FAILED', 'STALE_VERIFICATION', 'VERIFICATION_EXPIRED', 'VERIFICATION_REPLAY', 'INVALID_ACK'].includes(value)) return 'danger';
  return 'neutral';
}
function badge(value, text) { return '<span class="tag ' + tone(value) + '">' + esc(text || labels[value] || value) + '</span>'; }
function clock(value) {
  if (!value || Number.isNaN(Date.parse(value))) return '—';
  return new Intl.DateTimeFormat('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(value));
}
function dateTime(value) {
  if (!value || Number.isNaN(Date.parse(value))) return 'Chưa đồng bộ';
  return new Intl.DateTimeFormat('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(value));
}
function number(value) {
  return typeof value === 'number' && Number.isFinite(value)
    ? new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 1 }).format(value) : '—';
}
function scheduleTime(schedule) { return String(schedule.hour).padStart(2, '0') + ':' + String(schedule.minute).padStart(2, '0'); }
function message(selector, text, kind = '') {
  const element = $(selector) || (selector === '#login-result' ? $('#session') : null);
  if (!element) return;
  element.textContent = text;
  element.hidden = !text;
  element.classList.remove('success', 'danger');
  if (kind) element.classList.add(kind);
}
function showView(view, updateHash = true) {
  if (!views.includes(view) || (view === 'refill' && !caregiver)) view = 'overview';
  currentView = view;
  for (const name of views) $('#view-' + name).hidden = name !== view;
  document.querySelectorAll('.main-nav [data-view]').forEach(button => {
    const active = button.dataset.view === (view === 'devices' ? 'overview' : view);
    button.classList.toggle('active', active);
    if (active) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');
  });
  document.querySelectorAll('.subnav [data-view]').forEach(button =>
    button.classList.toggle('active', button.dataset.view === (view === 'devices' ? 'devices' : 'overview'))
  );
  if (updateHash && location.hash !== '#' + view) history.replaceState(null, '', '#' + view);
}
async function api(url, body) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);
  try {
    const response = await fetch(url, {
      method: body ? 'POST' : 'GET', cache: 'no-store', signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: 'Bearer ' + token } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {})
    });
    const data = await response.json();
    if (!response.ok) {
      const error = new Error(labels[data.result] || ({
        'authentication required': 'Vui lòng nhập khóa truy cập.',
        'device not assigned to identity': 'Bạn chưa được phân quyền cho hộp này.',
        'caregiver role required': 'Chức năng dành cho người chăm sóc.',
        'MQTT broker unavailable': 'Chưa kết nối được thiết bị. Vui lòng thử lại.',
        'device must be online before refill': 'Hộp cần trực tuyến trước khi bắt đầu nạp.',
        'device must synchronize UTC before refill': 'Hộp chưa đồng bộ giờ UTC. Giữ simulator chạy và thử lại sau heartbeat.',
        'refill session already exists': 'Đã có phiên nạp. Kết thúc phiên hoặc chờ hết hạn rồi xác minh lại.',
        'valid verification required before confirm': 'Vui lòng xác minh lại trước khi nạp.'
      }[data.error]) || data.error || 'Không thể tải dữ liệu.');
      error.status = response.status;
      throw error;
    }
    return data;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('Quá thời gian chờ. Kiểm tra trạng thái trước khi gửi lại.');
    throw error;
  } finally { clearTimeout(timeout); }
}
function resetVerification(edited = false, cancelSession = true) {
  const hadVerification = Boolean(verification);
  if (cancelSession && refillSessionId && verification) {
    const oldActor = verificationContext ? JSON.parse(verificationContext).actor_id : '';
    api('/api/refill/end', {verification_id:verification, actor_id:oldActor}).catch(() => {});
  }
  verification = null;
  refillSessionId = null;
  $('#confirm').disabled = true;
  $('#authorize-refill').disabled = true;
  $('#end-refill').disabled = true;
  message('#refill-session','');
  if (edited && hadVerification) message('#refill-result', 'Thông tin đã thay đổi. Vui lòng xác minh lại.');
}
function refillBody() {
  return {
    actor_id: $('#actor').value.trim(), box_id: selected(), patient_id: $('#patient').value.trim(),
    slot_id: Number($('#slot').value), medication_code: $('#medication').value.trim()
  };
}
function renderRefillContext() {
  const slot = Number($('#slot').value);
  const assignment = currentSlots.find(item => item.slot_id === slot);
  $('#refill-context').textContent = 'Hộp ' + selected() + ' · Ngăn ' + slot + ' · ' + (assignment ? (assignment.medication_name || assignment.medication_code) + ' (' + assignment.medication_code + ')' : 'Chưa gán');
}
function renderRefillSession(session) {
  if (!verification || session?.verification_id !== verification) return;
  refillSessionId = session.session_id;
  const fresh = Date.parse(session.expires_at)>Date.now();
  const awaitingClose = fresh && session.status==='CLOSED' && session.end_uptime_ms==null;
  $('#authorize-refill').disabled = true;
  $('#end-refill').disabled = !fresh || (!['PENDING','ACTIVE'].includes(session.status) && !awaitingClose);
  $('#confirm').disabled = !fresh || !['ACTIVE','CLOSED'].includes(session.status) || session.opened_count<1;
  const text = !fresh ? 'Phiên nạp đã hết hạn.' : session.status==='PENDING' ? 'Đang chờ thiết bị cho phép nạp…' :
    session.status==='ACTIVE' ? 'Được phép nạp ngăn '+session.slot_id+(session.opened_count ? ' · Đã ghi nhận mở ngăn.' : ' · Hãy mở đúng ngăn.') :
    awaitingClose ? 'Chờ thiết bị kết thúc phiên; có thể gửi lại yêu cầu hoặc chờ tự hết hạn.' : session.status==='CLOSED' ? 'Thiết bị đã kết thúc phiên nạp.' : 'Thiết bị từ chối phiên nạp. Kiểm tra đồng bộ giờ UTC và xác minh lại.';
  message('#refill-session',text);
}
function renderCareAlerts(result) {
  const entries=result?.items || [];
  $('#alerts-panel').hidden=!entries.length;
  $('#care-alerts').innerHTML=entries.map(item=>'<div class="care-alert-row '+esc(item.severity)+'"><div><strong>'+esc(item.device_id)+' · '+esc(labels[item.kind] || item.kind)+
    '</strong><small>'+(item.slot_id ? 'Ngăn '+item.slot_id+' · ' : '')+esc(dateTime(item.created_at))+(item.acknowledged_by ? ' · '+esc(item.acknowledged_by) : '')+'</small></div>'+
    (caregiver && item.status==='OPEN' ? '<button class="button secondary" onclick="acknowledgeAlert('+item.alert_id+',\''+
    (['WRONG_SLOT','UNSCHEDULED_OPEN','AMBIGUOUS_OPEN'].includes(item.kind) ? 'resolve' : 'acknowledge')+'\')">'+
    (['WRONG_SLOT','UNSCHEDULED_OPEN','AMBIGUOUS_OPEN'].includes(item.kind) ? 'Đã kiểm tra' : 'Tiếp nhận')+'</button>' : badge(item.status))+'</div>').join('');
}
async function acknowledgeAlert(id,action) {
  try { await api('/api/alerts/'+id+'/ack',{actor_id:$('#actor').value.trim(),action});load(); }
  catch(error) {message('#error',error.message);}
}
function renderDevices(devices, device) {
  $('#devices').innerHTML = devices.map(item => '<article class="surface device-card"><div class="section-heading"><h2>' +
    esc(item.device_id) + '</h2><span class="tag ' + (item.status === 'online' ? 'success' : 'neutral') + '">' +
    (item.status === 'online' ? 'Đã kết nối' : 'Ngoại tuyến') + '</span></div><div class="device-info"><div>Người dùng<strong>' +
    esc(item.patient_name || item.patient_id) + '</strong></div><div>Trạng thái<strong>' + esc(labels[item.state] || 'Chưa có dữ liệu') +
    '</strong></div><div>Giờ UTC<strong>' + (item.utc_synced ? 'Đã đồng bộ' : 'Đang chờ đồng bộ') + '</strong></div><div>Cập nhật lần cuối<strong>' + esc(dateTime(item.last_seen)) +
    '</strong></div><div>Hàng đợi<strong>' + esc(item.queue_depth || 0) + ' chờ · ' + esc(item.queue_dropped || 0) + ' bỏ do đầy</strong></div>' +
    (Number.isInteger(item.wifi_rssi) ? '<div>Wi-Fi<strong>' + esc(item.wifi_rssi) + ' dBm</strong></div>' : '') +
    (item.ip_address ? '<div>Địa chỉ IP<strong>' + esc(item.ip_address) + '</strong></div>' : '') + '</div></article>').join('');
  const online = device?.status === 'online';
  $('#connection').classList.toggle('online', online);
  $('#connection').replaceChildren(Object.assign(document.createElement('i'), { ariaHidden: 'true' }),
    document.createTextNode(selected() + ' · ' + (online ? 'Đã kết nối' : 'Ngoại tuyến')));
  $('#hero-device').textContent = selected();
  $('#hero-patient').textContent = device?.patient_name || device?.patient_id || 'Chưa gán người dùng';
  $('#hero-state').textContent = labels[device?.state] || 'Chưa có trạng thái';
  $('#control-device').textContent = selected();
}
function renderSchedules(schedules, slots, device) {
  const civil = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Ho_Chi_Minh', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date()).split(':').map(Number);
  const minute = Number.isInteger(device?.device_local_minute) ? device.device_local_minute : civil[0] * 60 + civil[1];
  const next = schedules.filter(schedule => schedule.enabled).sort((a, b) =>
    ((a.hour * 60 + a.minute - minute + 1440) % 1440) - ((b.hour * 60 + b.minute - minute + 1440) % 1440)
  )[0];
  $('#next-time').textContent = next ? scheduleTime(next) : '—';
  $('#next-reminder').textContent = next ? 'Ngăn ' + next.slot_id + ' · ' + (next.medication_name || next.medication_code) : 'Chưa có lịch nhắc';
  $('#assigned-count').innerHTML = '<span>' + slots.length + '</span><small>/ 3 ngăn</small>';
  $('#assignment-note').textContent = schedules.filter(schedule => schedule.enabled).length + ' lịch nhắc đang bật';
  $('#schedule-count').textContent = schedules.length + ' lịch';
  $('#slots').innerHTML = [1, 2, 3].map(slot => {
    const assignment = slots.find(item => item.slot_id === slot);
    const times = schedules.filter(schedule => schedule.slot_id === slot && schedule.enabled).sort((a, b) => a.hour * 60 + a.minute - b.hour * 60 - b.minute);
    return '<article class="slot-card"><div class="slot-top"><span class="slot-number">0' + slot + ' / NGĂN ' + slot +
      '</span><span class="tag ' + (assignment ? 'neutral' : 'warning') + '">' + (assignment ? 'Đã gán' : 'Trống') +
      '</span></div><h3>' + esc(assignment?.medication_name || assignment?.medication_code || 'Chưa gán') + '</h3><p>' +
      esc(assignment?.medication_code || '—') + '</p><div>' +
      times.map(schedule => '<span class="slot-time' + (schedule.schedule_id === next?.schedule_id ? ' next' : '') + '">' + scheduleTime(schedule) + '</span>').join('') + '</div></article>';
  }).join('');
  $('#schedules').innerHTML = schedules.map(schedule => '<tr><td><strong>' + esc(schedule.schedule_id) + '</strong></td><td>Ngăn ' +
    schedule.slot_id + '</td><td>' + esc(schedule.medication_name || schedule.medication_code) + '<small>' + esc(schedule.medication_code) + '</small></td><td><strong>' + scheduleTime(schedule) +
    '</strong></td><td>' + badge(schedule.enabled ? 'APPLIED' : 'IDLE', schedule.enabled ? 'Đang bật' : 'Đã tắt') + '</td></tr>').join('') ||
    '<tr><td colspan="5" class="empty">Chưa có lịch nhắc.</td></tr>';
}
function renderEvents(events, occurrences, recentEvents) {
  $('#recent-events').innerHTML = recentEvents.slice(0, 4).map(event => '<div class="activity-row"><div class="activity-copy"><strong>' +
    esc(labels[event.event] || event.event) + '</strong><small>' + (event.slot_id ? 'Ngăn ' + event.slot_id : 'Môi trường') +
    (event.schedule_id && !['NONE', 'ENV', 'AMBIGUOUS'].includes(event.schedule_id) ? ' · ' + esc(event.schedule_id) : '') +
    '</small></div>' + badge(event.event) + '<time>' + esc(dateTime(event.occurred_at || event.received_at)) + '</time></div>').join('') ||
    '<p class="empty">Chưa có hoạt động.</p>';
  $('#events').innerHTML = events.map(event => '<tr><td><strong>' + esc(clock(event.occurred_at || event.received_at)) +
    '</strong><small>' + esc(dateTime(event.occurred_at || event.received_at)) + '</small></td><td>' +
    badge(event.event) + '</td><td>' + (event.slot_id ? 'Ngăn ' + event.slot_id : 'Môi trường') +
    '<small>' + esc(event.schedule_id && !['NONE', 'ENV', 'AMBIGUOUS'].includes(event.schedule_id) ? event.schedule_id : '—') +
    '</small></td><td>' + (event.delay_minutes > 0 ? event.delay_minutes + ' phút' : '—') + '</td></tr>').join('') ||
    '<tr><td colspan="4" class="empty">Chưa có hoạt động.</td></tr>';
  $('#occurrences').innerHTML = occurrences.map(item => '<div class="result-row"><span class="result-time">' +
    esc(clock(item.scheduled_at)) + '</span><div class="result-main"><strong>' + esc(item.schedule_id) + ' · Ngăn ' + item.slot_id +
    '</strong><small>' + esc(item.confirmed_at ? 'Xác nhận lúc ' + clock(item.confirmed_at) +
      (item.delay_minutes > 0 ? ' · Trễ ' + item.delay_minutes + ' phút' : '') : dateTime(item.scheduled_at)) +
    '</small></div>' + badge(item.current_outcome) + '</div>').join('') || '<p class="empty">Chưa có kết quả nhắc thuốc.</p>';
}
function renderEnvironment(readings, device) {
  const latest = readings[0];
  const storage = device?.storage_status || 'PENDING';
  const alert = Boolean(latest && (!latest.sensor_ok || ['WARNING', 'STORAGE_WARNING', 'SENSOR_ERROR'].includes(storage)));
  const storageLabel = !latest ? 'Chưa có số đo' : !latest.sensor_ok || storage === 'SENSOR_ERROR' ? 'Lỗi cảm biến' : alert ? 'Vượt ngưỡng' : storage === 'PENDING' ? 'Đang đánh giá' : 'Cập nhật ' + clock(latest.sampled_at || latest.received_at);
  $('#environment-value').closest('.metric').classList.toggle('metric-alert', alert);
  $('#environment-value').innerHTML = latest?.sensor_ok
    ? esc(number(latest.temperature_c)) + '°<small>· ' + esc(number(latest.humidity_percent)) + '% RH</small>' : '—';
  $('#environment-status').textContent = storageLabel;
  $('#environment').innerHTML = '<div class="section-heading"><h2>Môi trường</h2>' +
    (latest ? badge(alert ? 'STORAGE_WARNING' : 'IDLE', storageLabel) : '') + '</div>' +
    (latest ? '<div class="environment-detail"><strong>' + (latest.sensor_ok ? esc(number(latest.temperature_c)) + ' °C' : '—') +
      '</strong><span>' + (latest.sensor_ok ? esc(number(latest.humidity_percent)) + '% RH' : 'Lỗi cảm biến') +
      '</span></div><details><summary>Số đo gần đây</summary>' + readings.slice(0, 5).map(item => '<p>' +
      esc(dateTime(item.sampled_at || item.received_at)) + ' · ' + (item.sensor_ok ?
        esc(number(item.temperature_c)) + ' °C / ' + esc(number(item.humidity_percent)) + '% RH' : 'Lỗi cảm biến') + '</p>').join('') + '</details>' :
      '<p class="empty">Chưa có số đo.</p>');
}
function renderAudit(audit, device) {
  $('#audit').innerHTML = audit.filter(item => item.box_id === device).slice(0, 8).map(item =>
    '<div class="activity-row"><div class="activity-copy"><strong>' + esc(labels[item.result] || item.result) +
    '</strong><small>' + esc(item.actor_id) + ' · ' + esc(item.patient_id) + ' · Ngăn ' + item.slot_id +
    '</small></div><time>' + esc(dateTime(item.timestamp)) + '</time></div>').join('') || '<p class="empty">Chưa có lần nạp thuốc nào.</p>';
}
function renderCommands(commands) {
  $('#commands').innerHTML = commands.map(command => '<div class="command-row"><span>' +
    esc(labels[command.command] || command.command) + (Number.isFinite(command.ack_latency_ms) ? '<small> · ACK ' + esc(command.ack_latency_ms) + ' ms</small>' : '') + '</span>' + badge(command.status, command.status === 'PENDING' ? 'Chờ phản hồi' : null) + '</div>').join('');
  const latest = commands.find(command => command.command_id === lastCommandId);
  if (latest && latest.status !== 'PENDING') message('#command-result',
    latest.status === 'APPLIED' ? 'Thiết bị đã phản hồi.' : labels[latest.status] || latest.status,
    latest.status === 'APPLIED' ? 'success' : 'danger');
}
function renderPagination(name, result) {
  const target = $('#' + name + '-pagination');
  listPages[name] = result.page;
  if (result.pages <= 1) { target.replaceChildren(); return; }
  const makeButton = (page, text, disabled = false, active = false) =>
    '<button type="button" class="page-button' + (active ? ' active' : '') + '" data-page-list="' +
    name + '" data-page="' + page + '"' + (disabled ? ' disabled' : '') +
    (active ? ' aria-current="page"' : '') + '>' + text + '</button>';
  const visible = [...new Set([1, result.page - 1, result.page, result.page + 1, result.pages])].filter(page => page >= 1 && page <= result.pages).sort((a, b) => a - b);
  let previous = 0;
  const buttons = visible.map(page => {
    const gap = previous && page > previous + 1 ? '<span aria-hidden="true">…</span>' : '';
    previous = page;
    return gap + makeButton(page, page, false, page === result.page);
  }).join('');
  target.innerHTML = '<span class="page-info">' + ((result.page - 1) * result.page_size + 1) + '–' +
    Math.min(result.page * result.page_size, result.total) + ' / ' + result.total + '</span>' +
    makeButton(result.page - 1, 'Trước', result.page === 1) + buttons +
    makeButton(result.page + 1, 'Sau', result.page === result.pages);
}

async function loadHistory(force = false) {
  if (currentView !== 'history' || historyLoading || accessBlocked || loginInProgress) return;
  const device = selected(), version = authVersion, hours = $('#history-hours').value;
  const key = device + ':' + hours + ':' + version;
  if (!force && key === historyKey && Date.now() - historyFetchedAt < 10000) return;
  historyLoading = true;
  try {
    const result = await api('/api/devices/' + encodeURIComponent(device) + '/environment/history?hours=' + hours);
    if (device !== selected() || version !== authVersion || hours !== $('#history-hours').value) return;
    historyKey = key; historyFetchedAt = Date.now();
    const points = result.items;
    if (!points.length) { $('#environment-chart').innerHTML = '<p class="empty">Chưa có mẫu hợp lệ trong khoảng đã chọn.</p>'; return; }
    const plot = (field, title, color, minRange) => {
      const values = points.map(p => p[field]);
      const low = Math.floor(Math.min(...values) - minRange), high = Math.ceil(Math.max(...values) + minRange);
      const x = i => 50 + (points.length === 1 ? 320 : i * 640 / (points.length - 1));
      const y = v => 145 - (v - low) * 110 / (high - low);
      return '<svg viewBox="0 0 740 180" role="img" aria-label="' + title + '"><text x="50" y="18">' + title + '</text>' +
        '<path d="M50 30V145H700" fill="none" stroke="#aaa"/><text x="4" y="40">' + high + '</text><text x="4" y="145">' + low + '</text>' +
        '<polyline points="' + values.map((v,i) => x(i)+','+y(v)).join(' ') + '" fill="none" stroke="' + color + '" stroke-width="2.5"/>' +
        values.map((v,i) => '<circle cx="'+x(i)+'" cy="'+y(v)+'" r="3" fill="'+color+'"><title>'+esc(number(v))+'</title></circle>').join('') +
        '<text x="50" y="170">' + esc(clock(points[0].received_at)) + '</text><text x="640" y="170">' + esc(clock(points.at(-1).received_at)) + '</text></svg>';
    };
    $('#environment-chart').innerHTML = plot('temperature_c','Nhiệt độ (°C)','#e05224',1) + plot('humidity_percent','Độ ẩm (% RH)','#0757ed',2);
  } catch (error) { $('#environment-chart').textContent = error.message; }
  finally { historyLoading = false; }
}
function renderSession(session) {
  $('#session').textContent = session.auth_enabled
    ? session.identity.actor_id + ' · ' + roleLabels[session.identity.role] : 'Không yêu cầu khóa truy cập.';
  caregiver = !session.auth_enabled || ['nurse', 'admin'].includes(session.identity.role);
  $('#settings-open').textContent = session.auth_enabled
    ? session.identity.actor_id + ' · ' + roleLabels[session.identity.role] : 'Tài khoản · Chưa bật xác thực';
  $('#settings-open').title = $('#session').textContent;
  if ($('#simulator-panel')) $('#simulator-panel').hidden = !session.local_simulation || !caregiver;
  document.querySelectorAll('.caregiver-control').forEach(button => { button.hidden = !caregiver; });
  $('#refill-panel').hidden = !caregiver;
  $('#actor-field').hidden = session.auth_enabled;
  if (session.auth_enabled) $('#actor').value = session.identity.actor_id;
  if (!caregiver && currentView === 'refill') showView('overview');
}
async function load() {
  if (loginInProgress) { refreshQueued = true; return; }
  if (loading) { refreshQueued = true; return; }
  loading = true;
  const version = authVersion;
  let device = selected();
  try {
    if (!bootstrapReady) {
      const assigned = await api('/api/devices');
      if (version !== authVersion) return;
      if (!assigned.length) throw new Error('Chưa có hộp thuốc được phân công.');
      knownDevices = assigned;
      $('#device').replaceChildren(...assigned.map(item => new Option(item.device_id, item.device_id)));
      if (assigned.some(item => item.device_id === device)) $('#device').value = device;
      else {
        device = selected();
        $('#patient').value = assigned.find(item => item.device_id === device)?.patient_id || '';
        resetVerification();
      }
      bootstrapReady = true;
    }
    const query = new URLSearchParams({ page_size: String(pageSize) });
    query.set('actor_id',$('#actor').value.trim());
    for (const [name, page] of Object.entries(listPages)) query.set(name + '_page', String(page));
    const snapshot = await api('/api/devices/' + encodeURIComponent(device) + '/live?' + query);
    if (version !== authVersion) return;
    if (device !== selected()) { refreshQueued = true; return; }
    const { session, devices, events, readings, schedules, occurrences, slots, audit, commands, recent } = snapshot;
    renderSession(session);
    knownDevices = devices;
    const options = devices.map(item => item.device_id);
    if (JSON.stringify(options) !== JSON.stringify([...$('#device').options].map(option => option.value))) {
      $('#device').replaceChildren(...devices.map(item => new Option(item.device_id, item.device_id)));
      $('#device').value = device;
    }
    currentSlots = slots;
    const current = snapshot.device;
    renderChanged('devices', devices, () => renderDevices(devices, current));
    renderChanged('schedules', [schedules, slots, current.device_local_minute, Math.floor(Date.now()/60000)], () => renderSchedules(schedules, slots, current));
    renderChanged('events', [events, occurrences, recent], () => renderEvents(events.items, occurrences.items, recent));
    renderChanged('events-page', events, () => renderPagination('events', events));
    renderChanged('occurrences-page', occurrences, () => renderPagination('occurrences', occurrences));
    renderChanged('environment', [readings, current.storage_status], () => renderEnvironment(readings, current));
    loadHistory();
    renderChanged('audit', audit, () => renderAudit(audit.items, device));
    renderChanged('audit-page', audit, () => renderPagination('audit', audit));
    renderChanged('commands', [commands, lastCommandId], () => renderCommands(commands.items));
    renderChanged('commands-page', commands, () => renderPagination('commands', commands));
    renderRefillContext();
    renderRefillSession(snapshot.refill_session);
    renderChanged('care-alerts',[snapshot.alerts,caregiver],()=>renderCareAlerts(snapshot.alerts));
    if (snapshot.alerts) renderChanged('alerts-page',snapshot.alerts,()=>renderPagination('alerts',snapshot.alerts));
    message('#error', '');
  } catch (error) {
    if (version !== authVersion) return;
    message('#error', error.message);
    $('#connection').classList.remove('online');
    $('#connection').textContent = error.status === 401 ? 'Cần đăng nhập' : 'Chưa kết nối';
    renderCache.clear();
    if (error.status === 403) bootstrapReady = false;
    if (error.status === 401) {
      $('#settings-open').textContent = 'Chưa đăng nhập';
      $('#session').textContent = 'Chưa đăng nhập';
      accessBlocked = true; bootstrapReady = false;
      if (!authPrompted) {
        authPrompted = true;
        if (!$('#settings-dialog').open) $('#settings-dialog').showModal();
      }
    }
  } finally {
    loading = false;
    if (refreshQueued && !accessBlocked) { refreshQueued = false; load(); }
  }
}
async function sendCommand(command) {
  try {
    const response = await api('/api/devices/' + encodeURIComponent(selected()) + '/commands', { command });
    lastCommandId = response.command_id;
    message('#command-result', 'Đã gửi yêu cầu. Đang chờ thiết bị phản hồi…');
    load();
  } catch (error) { message('#command-result', error.message, 'danger'); }
}
async function verifyRefill(event) {
  event.preventDefault();
  resetVerification();
  try {
    const body = refillBody();
    const response = await api('/api/refill/verify', body);
    if (response.result === 'VERIFIED') {
      verification = response.verification_id;
      verificationContext = JSON.stringify(body);
      expiresAt = Date.parse(response.expires_at);
      $('#authorize-refill').disabled = false;
      message('#refill-result', 'Mã thuốc phù hợp. Bắt đầu nạp để cho phép mở ngăn.', 'success');
    } else message('#refill-result', labels[response.result] || response.result, 'danger');
  } catch (error) { message('#refill-result', error.message, 'danger'); }
  load();
}
async function authorizeRefill() {
  if (!verification || Date.now()>=expiresAt) {resetVerification();return;}
  $('#authorize-refill').disabled=true;
  try {
    const result=await api('/api/refill/authorize',{verification_id:verification,actor_id:$('#actor').value.trim()});
    refillSessionId=result.session_id;
    $('#end-refill').disabled=false;
    message('#refill-session','Đang chờ thiết bị cho phép nạp…');
    load();
  } catch(error) {$('#authorize-refill').disabled=false;message('#refill-result',error.message,'danger');}
}
async function endRefill() {
  if (!verification) return;
  try {
    await api('/api/refill/end',{verification_id:verification,actor_id:$('#actor').value.trim()});
    message('#refill-session','Đã yêu cầu kết thúc phiên nạp.');load();
  } catch(error) {message('#refill-result',error.message,'danger');}
}
async function confirmRefill() {
  if (!verification || verificationContext !== JSON.stringify(refillBody()) || Date.now() >= expiresAt) {
    resetVerification();
    message('#refill-result', 'Vui lòng xác minh lại thông tin.', 'danger');
    return;
  }
  const id = verification;
  resetVerification(false,false);
  try {
    const response = await api('/api/refill/confirm', { actor_id: $('#actor').value, verification_id: id });
    message('#refill-result', labels[response.result] || response.result, response.result === 'CONFIRMED' ? 'success' : 'danger');
    if (response.session_close) message('#refill-session',response.session_close.status==='PUBLISH_FAILED' ?
      'Chưa gửi được lệnh kết thúc tới hộp. Phiên thiết bị sẽ tự hết hạn.' : 'Đã yêu cầu thiết bị kết thúc phiên. Theo dõi ACK ở mục Thiết bị.');
  } catch (error) { message('#refill-result', error.message, 'danger'); }
  load();
}

document.addEventListener('click', event => {
  const button = event.target.closest('[data-page-list]');
  if (!button || button.disabled || !(button.dataset.pageList in listPages)) return;
  listPages[button.dataset.pageList] = Number(button.dataset.page);
  load();
});
document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => showView(button.dataset.view)));
window.addEventListener('hashchange', () => showView(location.hash.slice(1), false));
$('#device').addEventListener('change', () => {
  resetVerification();
  message('#refill-result', '');
  message('#command-result', '');
  lastCommandId = null;
  for (const name of Object.keys(listPages)) listPages[name] = 1;
  currentSlots = []; renderCache.clear();
  $('#patient').value = knownDevices.find(device => device.device_id === selected())?.patient_id || '';
  renderRefillContext();
  load();
});
$('#refill-form').addEventListener('input', () => { resetVerification(true); renderRefillContext(); });
$('#slot').addEventListener('change', () => { resetVerification(true); renderRefillContext(); });
$('#history-hours').addEventListener('change', () => loadHistory(true));
$('#settings-open').addEventListener('click', () => $('#settings-dialog').showModal());
$('#settings-close').addEventListener('click', () => $('#settings-dialog').close());
$('#login').addEventListener('click', async () => {
  if (loginInProgress) return;
  loginInProgress = true;
  authVersion++;
  $('#login').disabled = true;
  try {
    message('#login-result', 'Đang kiểm tra khóa truy cập…');
    token = $('#access-token').value.trim();
    $('#access-token').value = '';
    authPrompted = false; bootstrapReady = false; accessBlocked = false; renderCache.clear();
    resetVerification();
    const session = await api('/api/session');
    renderSession(session);
    message('#login-result', session.auth_enabled
      ? 'Đăng nhập thành công: ' + session.identity.actor_id + ' · ' + roleLabels[session.identity.role]
      : 'Máy chủ chưa bật xác thực. Không cần nhập khóa.', 'success');
    message('#error', '');
  } catch (error) {
    accessBlocked = true;
    $('#session').textContent = 'Chưa đăng nhập';
    $('#settings-open').textContent = 'Chưa đăng nhập';
    message('#login-result', error.status === 401 ? 'Khóa truy cập không hợp lệ hoặc chưa được nhập.' : error.message, 'danger');
  } finally {
    loginInProgress = false;
    $('#login').disabled = false;
    if (!accessBlocked) load();
  }
});
$('#access-token').addEventListener('keydown', event => {
  if (event.key === 'Enter') { event.preventDefault(); $('#login').click(); }
});
document.querySelectorAll('[data-simulator]').forEach(button => button.addEventListener('click', async () => {
  button.disabled = true;
  try {
    await api('/api/simulator/action', { box_id: selected(), action: button.dataset.simulator });
    message('#simulator-result', 'Đã thực hiện trên ' + selected() + '.', 'success');
    load();
  } catch (error) { message('#simulator-result', error.message, 'danger'); }
  finally { button.disabled = false; }
}));
$('#settings-dialog').addEventListener('click', event => {
  if (event.target === $('#settings-dialog')) {
    const rect = event.target.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) event.target.close();
  }
});
setInterval(() => {
  if (verification && Date.now() >= expiresAt) {
    resetVerification();
    message('#refill-result', 'Xác minh đã hết hạn. Vui lòng xác minh lại.');
  }
  if (document.visibilityState === 'visible' && !accessBlocked) load();
}, 1000);
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible' && !accessBlocked) load();
});
showView(location.hash.slice(1) || 'overview', false);
load();
