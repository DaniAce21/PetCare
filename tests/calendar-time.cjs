// Ejecutar: node tests/calendar-time.cjs. No requiere dependencias ni navegador.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/app.js', 'utf8');
class FixedDate extends Date {
 constructor(...args) { super(...(args.length ? args : ['2030-07-09T02:00:00Z'])); }
}
const context = vm.createContext({Date: FixedDate, Intl, assert, URLSearchParams});
vm.runInContext(source.slice(0, source.indexOf('let toastTimer;')), context);
vm.runInContext(`
 assert.equal(today(), '2030-07-08');
 assert.equal(futureSlot('2030-07-08', '21:59'), false);
 assert.equal(futureSlot('2030-07-08', '22:00'), false);
 assert.equal(futureSlot('2030-07-08', '22:01'), true);
 assert.equal(futureSlot('2030-07-09', '09:00'), true);
 assert.ok(!calendarAdd('2030-07-07').includes('data-action'));
 assert.ok(!calendarAdd('2030-07-08', '21:00').includes('data-action'));
 assert.ok(calendarAdd('2030-07-08', '23:00').includes('calendar-add'));
 assert.ok(calendarAdd('2030-07-09').includes('calendar-add'));
`, context);
// Renderizar realmente las vistas históricas, conservando sus eventos.
const elements = {};
context.document = {querySelector: q => elements[q] ||= {innerHTML: '',textContent: ''}, querySelectorAll: () => []};
context.events = [{id:1,fecha:'2030-07-01',hora_inicio:'10:00',hora_termino:'10:30',mascota_nombre:'Luna',veterinario_nombre:'Vet',veterinario:1,estado:'Completada'}];
vm.runInContext('async function all() { return events; }', context);
vm.runInContext(source.slice(source.indexOf('function calendarRange()'), source.indexOf('async function appointmentDetail(')), context);
(async () => {
 for (const mode of ['day','week','month']) {
  await vm.runInContext(`state.view='agenda';state.calendarMode='${mode}';state.calendarDate=parseDate('2030-07-01');loadCalendar();`, context);
  const html = elements['#calendar'].innerHTML;
  assert.ok(html.includes('Luna'), mode);
  if(mode !== 'month')assert.ok(!html.includes('calendar-add'), mode);
  if(mode === 'month')assert.ok(html.includes('past'), mode);
 }
 console.log('Calendario: hora de Santiago, límites estrictos e historial: OK');
})().catch(error => {console.error(error);process.exitCode=1;});

// El detalle histórico conserva la consulta y oculta acciones destructivas.
context.api = async () => ({id:1,fecha:'2030-07-01',hora_inicio:'10:00',hora_termino:'10:30',estado:'Completada',mascota:1,mascota_nombre:'Luna'});
context.showModal = (_title, html) => {
 assert.ok(html.includes('solo consulta'));
 for(const action of ['modify-appointment','cancel-appointment','delete-appointment']) {
  assert.ok(!html.includes(`data-action="${action}"`), action);
 }
 assert.ok(html.includes('detail-pet'));
};
vm.runInContext("state.profile={rol:'Administrador'};", context);
vm.runInContext(source.slice(source.indexOf('async function appointmentDetail('), source.indexOf('async function deleteRecord(')), context);
vm.runInContext('appointmentDetail(1)', context).catch(error => {console.error(error);process.exitCode=1;});
