'use strict';
const $ = (q, root = document) => root.querySelector(q);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icons = {
 dashboard:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
 agenda:'M4 5h16v16H4z M4 10h16 M8 3v4 M16 3v4 M8 14h2 M14 14h2 M8 17h2',
 pets:'M12 20c-4-2-9-6-9-10a5 5 0 0 1 9-3 5 5 0 0 1 9 3c0 4-5 8-9 10z',
 tutors:'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0 M4 21v-3a8 8 0 0 1 16 0v3',
 vaccines:'M9 3h6v6h6v6h-6v6H9v-6H3V9h6z',
 reminders:'M5 17h14l-2-4V8a5 5 0 0 0-10 0v5z M10 21h4',
 vets:'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0 M4 21v-3a8 8 0 0 1 16 0v3 M12 13v8 M9 18h6',
 fichas:'M6 3h12v18H6z M9 8h6 M9 12h6 M9 16h4',
 availability:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M12 7v5l4 2',
 users:'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0 M4 21v-3a8 8 0 0 1 16 0v3',
 profile:'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0 M4 21v-3a8 8 0 0 1 16 0v3',
};
const icon = name => `<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${icons[name] || icons.pets}"/></svg>`;
const labels = {dashboard:'Resumen',agenda:'Agenda médica',pets:'Mascotas y fichas',tutors:'Tutores',vaccines:'Vacunación',reminders:'Recordatorios',vets:'Profesionales',fichas:'Fichas clínicas',availability:'Disponibilidad',users:'Usuarios',profile:'Mi perfil'};
const endpoints = {pets:'mascotas',tutors:'tutores',vaccines:'vacunas',reminders:'recordatorios',vets:'veterinarios',fichas:'fichas',availability:'disponibilidades',users:'usuarios',agenda:'citas'};
const state = {view:'dashboard',profile:null,refs:{},list:null,page:1,search:'',filter:'',calendarMode:'week',calendarDate:new Date(),calendarVet:'',calendarStatus:'',events:[],loading:false};
const isAdmin = () => state.profile?.rol === 'Administrador';
const isClinical = () => ['Administrador','Veterinario'].includes(state.profile?.rol);
const ownVet = id => isAdmin() || Number(id) === state.profile?.veterinario;
const canWrite = view => isAdmin() || (['fichas','vaccines','availability'].includes(view) ? isClinical() : !['vets','users'].includes(view));
const dateISO = date => `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;
function clinicNow() {
 const parts=Object.fromEntries(new Intl.DateTimeFormat('en-CA',{timeZone:'America/Santiago',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(new Date()).map(p=>[p.type,p.value]));
 return {date:`${parts.year}-${parts.month}-${parts.day}`,time:`${parts.hour}:${parts.minute}:${parts.second}`};
}
const today = () => clinicNow().date;
const futureSlot = (date,time) => {const now=clinicNow();return date>now.date || (date===now.date && `${time}:00`>now.time);};
function calendarAdd(date,time='') {
 if(date<today())return '<span class="subtle">Solo consulta</span>';
 if(time&&!futureSlot(date,time))return '<span class="subtle">Horario transcurrido</span>';
 return button('+ Cita','calendar-add',`${date}|${time}`,'day-add');
}
const parseDate = date => new Date(`${date}T12:00:00`);
const fmt = value => value ? parseDate(value.slice(0,10)).toLocaleDateString('es-CL',{day:'numeric',month:'short',year:'numeric'}) : '—';
const hm = value => (value || '').slice(0,5);
const statusBadge = value => `<span class="badge ${value === 'Pendiente' ? 'warning' : value === 'Cancelada' ? 'neutral' : value === 'Completada' || value === 'Atendido' ? 'info' : ''}">${esc(value)}</span>`;
const button = (text, action, id='', cls='text-button') => `<button type="button" class="${cls}" data-action="${action}" data-id="${esc(id)}">${text}</button>`;
const empty = (title='No hay registros todavía.',text='Registra información para comenzar.') => `<div class="empty"><strong>${esc(title)}</strong>${esc(text)}</div>`;
let toastTimer;
function toast(message) { $('#toast').textContent=message; $('#toast').hidden=false; clearTimeout(toastTimer); toastTimer=setTimeout(()=>$('#toast').hidden=true,5500); }
function errorMessage(data) {
 if (typeof data === 'string') return data;
 if (Array.isArray(data)) return data.map(errorMessage).join(' ');
 return Object.entries(data || {}).map(([k,v]) => `${k === 'detail' || k === '__all__' || k === 'non_field_errors' ? '' : k+': '}${errorMessage(v)}`).join(' ');
}
async function api(path, options={}) {
 const headers = {'Accept':'application/json',...options.headers};
 if (options.body) {headers['Content-Type']='application/json'; headers['X-CSRFToken']=decodeURIComponent(document.cookie.split('; ').find(c=>c.startsWith('csrftoken='))?.split('=').slice(1).join('=') || '');}
 const response=await fetch(path,{...options,headers,credentials:'same-origin',cache:'no-store'});
 const data=response.status===204 ? null : await response.json().catch(()=>({detail:'Respuesta inválida del servidor.'}));
 if (!response.ok) throw new Error(errorMessage(data) || `Error ${response.status}`);
 return data;
}
async function all(endpoint, query='') {
 const results=[];
 let path=`/api/${endpoint}/?${query}`;
 while(path){const page=await api(path);results.push(...page.results);path=page.next;}
 return results;
}
async function loadRefs() {
 const names=['tutores','mascotas','veterinarios','disponibilidades'];
 if(isAdmin()) names.push('usuarios');
 const results=await Promise.all(names.map(name=>all(name)));
 names.forEach((name,i)=>state.refs[name]=results[i]);
}
function heading(title,description,actions='') {return `<div class="page-heading"><div><h1>${esc(title)}</h1><p>${esc(description)}</p></div><div class="actions">${actions}</div></div>`;}
function showModal(title,content) {
 $('#modal-title').textContent=title;$('#modal-content').innerHTML=content;
 if(!$('#modal').open) $('#modal').showModal();
}
function closeModal() {$('#modal').close();$('#modal-content').innerHTML='';}
function setBusy(button,busy) {if(button) button.disabled=busy;}
async function refresh() {
 if(state.loading || $('#modal').open || document.hidden)return;
 state.loading=true;
 try {
  if(state.view==='dashboard') await renderDashboard();
  else if(state.view==='agenda') await loadCalendar();
  else if(state.view!=='profile') await loadList();
  $('#sync').textContent='● Actualizado';$('#sync').classList.remove('connection-error');
 } catch(e){$('#sync').textContent='● Sin sincronizar';$('#sync').classList.add('connection-error');}
 finally{state.loading=false;}
}
async function navigate(view) {
 if(view==='fichas' && !isClinical()) return;
 if(view==='users' && !isAdmin())return;
 state.view=view;state.page=1;state.search='';state.filter='';
 document.title=`${labels[view]} · PetCare`;
 $('#breadcrumb').textContent=labels[view];
 document.querySelectorAll('[data-view]').forEach(b=>{b.classList.toggle('active',b.dataset.view===view);if(b.dataset.view===view)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
 $('#main').innerHTML='<div class="loading">Cargando información…</div>';
 try {
  if(view==='dashboard') await renderDashboard();
  else if(view==='agenda') {renderCalendarShell();await loadCalendar();}
  else if(view==='profile') renderProfile();
  else {renderListShell();await loadList();}
 } catch(e){$('#main').innerHTML=empty('No se pudo cargar esta sección.',e.message);toast(e.message);}
}
async function renderDashboard() {
 const data=await api('/api/dashboard/');
 if(state.view!=='dashboard')return;
 const dateLabel=parseDate(data.hoy).toLocaleDateString('es-CL',{weekday:'long',day:'numeric',month:'long',year:'numeric'});
 $('#main').innerHTML=heading('Una buena jornada empieza aquí.',dateLabel,button('+ Agendar cita','new-appointment','','primary'))+
 `<section class="welcome"><div><span class="eyebrow">TU CLÍNICA, CONECTADA</span><h2>Más organización. Más cuidado.</h2><p>Hoy tienes ${data.citas_hoy} citas y ${data.recordatorios_pendientes} recordatorios próximos o atrasados por atender.</p></div><div class="illustration" aria-hidden="true">${icon('pets')}</div></section>`+
 `<div class="stats">${[['Tutores registrados',data.tutores,'tutors','Una red de cuidados'],['Mascotas registradas',data.mascotas,'pets','Historias que acompañamos'],['Citas de hoy',data.citas_hoy,'agenda','Excluye citas canceladas'],['Vacunas pendientes',data.vacunas_pendientes,'vaccines','Vencidas y próximas en 7 días']].map(([label,value,i,desc])=>`<div class="stat"><div class="stat-top">${label}<span class="stat-icon">${icon(i)}</span></div><b>${value}</b><small>${desc}</small></div>`).join('')}</div>`+
 `<div class="columns"><div><section class="panel"><div class="panel-header"><h3>Próximas citas</h3>${button('Ver agenda →','go-agenda')}</div>${data.proximas_citas.length?`<div class="table-wrap"><table><thead><tr><th>PACIENTE</th><th>FECHA Y HORA</th><th>ESTADO</th><th></th></tr></thead><tbody>${data.proximas_citas.map(a=>`<tr><td><div class="pet-cell"><span class="pet-avatar">${icon('pets')}</span><div><strong>${esc(a.mascota_nombre)}</strong><small>${esc(a.veterinario_nombre)}</small></div></div></td><td>${fmt(a.fecha)}<small>${hm(a.hora_inicio)} – ${hm(a.hora_termino)}</small></td><td>${statusBadge(a.estado)}</td><td>${button('Ver','edit-appointment',a.id)}</td></tr>`).join('')}</tbody></table></div>`:empty('La agenda está despejada.','Crea la primera cita de la jornada.')}</section><section class="panel"><div class="panel-header"><h3>Actividad reciente</h3><span class="subtle">Cambios registrados en el sistema</span></div>${data.actividad.length?data.actividad.map(a=>`<div class="item-row"><span class="pet-avatar">${icon('fichas')}</span><div><strong>${esc(a.accion)} · ${esc(a.entidad)}</strong><p>${esc(a.usuario)} · ${new Date(a.fecha).toLocaleString('es-CL')}</p></div></div>`).join(''):empty('Sin actividad reciente.','Las operaciones de la API y del administrador se registrarán aquí.')}</section></div><div><section class="panel"><div class="panel-header"><h3>Cuidado preventivo</h3>${button('Ver todas','go-vaccines')}</div>${data.vacunas.length?data.vacunas.map(v=>`<div class="item-row"><span class="pet-avatar">${icon('vaccines')}</span><div><strong>${esc(v.mascota_nombre)}</strong><p>${esc(v.nombre)}<br>${fmt(v.fecha_proxima_dosis)}</p></div><span class="badge ${v.vencida?'danger':'warning'}">${v.vencida?'Atrasada':'Próxima'}</span></div>`).join(''):empty('Seguimiento al día.','No hay próximas dosis vencidas o dentro de 7 días.')}</section><div class="hint">La agenda se actualiza cada 15 segundos. El servidor comprueba cada reserva antes de guardarla.</div>${button('Consultar recordatorios →','go-reminders')}</div></div>`;
 $('#main').innerHTML+=`<section class="panel"><div class="panel-header"><h3>Citas de hoy</h3>${button('Ver agenda completa','go-agenda')}</div>${data.citas_del_dia.length?data.citas_del_dia.map(a=>`<div class="item-row"><div><strong>${esc(a.mascota_nombre)} · ${hm(a.hora_inicio)}</strong><p>${esc(a.veterinario_nombre)} · ${esc(a.estado)}</p></div>${button('Abrir cita','edit-appointment',a.id)}</div>`).join(''):empty('No hay citas para hoy.','')}</section>`;
 if(isClinical())$('#main').innerHTML+=`<section class="panel"><div class="panel-header"><h3>Consultas recientes</h3>${button('Ver fichas','go-fichas')}</div>${data.consultas_recientes.length?data.consultas_recientes.map(f=>`<div class="item-row"><div><strong>${esc(f.mascota_nombre)}</strong><p>${fmt(f.fecha_atencion)} · ${esc(f.motivo)}</p></div>${button('Ver atención','detail-record',f.id)}</div>`).join(''):empty('Sin consultas registradas.','')}</section>`;
}
const configs={
 tutors:{title:'Tutores',desc:'Las personas detrás de cada paciente.',new:'Registrar tutor',headers:['Nombre y RUT','Contacto','Dirección','Mascotas']},
 pets:{title:'Mascotas',desc:'Sus datos, su historia y todos sus cuidados.',new:'Registrar mascota',headers:['Paciente','Tutor','Nacimiento','Peso']},
 vets:{title:'Equipo veterinario',desc:'Profesionales, especialidades y disponibilidad.',new:'Registrar profesional',headers:['Profesional','Usuario','Especialidad','Estado']},
 availability:{title:'Disponibilidad',desc:'Franjas semanales de atención por profesional.',new:'Agregar franja',headers:['Profesional','Día','Inicio','Término']},
 fichas:{title:'Fichas clínicas',desc:'Atenciones y seguimiento médico de cada mascota.',new:'Registrar atención',headers:['Paciente','Fecha','Profesional','Motivo']},
 vaccines:{title:'Vacunación',desc:'Aplicaciones, próximas dosis y seguimiento preventivo.',new:'Registrar vacuna',headers:['Vacuna / paciente','Aplicación','Próxima dosis','Seguimiento']},
 reminders:{title:'Recordatorios',desc:'Vacunas y controles que necesitan seguimiento.',new:'Nuevo control',headers:['Paciente','Tipo / fecha','Mensaje','Estado']},
 users:{title:'Usuarios y roles',desc:'Administra el acceso del equipo de la clínica.',new:'Crear usuario',headers:['Usuario','Nombre','Rol','Estado']},
};
function filterOptions(view) {
 if(view==='vaccines')return [['','Todas las vacunas'],['vencidas','Atrasadas'],['proximas','Próximas en 7 días']];
 if(view==='reminders')return [['','Todos los estados'],['Pendiente','Pendientes'],['Atendido','Atendidos']];
 if(view==='pets')return [['','Todas las especies'],...['Perro','Gato','Ave','Conejo','Otro'].map(v=>[v,v])];
 if(['fichas','availability'].includes(view))return [['','Todos los profesionales'],...(state.refs.veterinarios||[]).map(v=>[v.id,v.nombre])];
 return [];
}
function renderListShell() {
 const view=state.view,c=configs[view],filters=filterOptions(view);
 $('#main').innerHTML=heading(c.title,c.desc,canWrite(view)?button('+ '+c.new,'new','','primary'):'')+
 `<div class="toolbar"><label class="search-label">Buscar<input id="search" type="search" aria-label="Buscar registros" placeholder="Buscar en ${c.title.toLowerCase()}…"></label>${filters.length?`<label>Filtrar<select id="list-filter">${filters.map(([value,label])=>`<option value="${esc(value)}">${esc(label)}</option>`).join('')}</select></label>`:''}<span class="subtle">Datos guardados en PostgreSQL</span></div><section class="panel" id="list-content"><div class="loading">Cargando…</div></section>`;
 let timer;
 $('#search').addEventListener('input',event=>{state.search=event.target.value;state.page=1;clearTimeout(timer);timer=setTimeout(()=>loadList().catch(e=>toast(e.message)),250);});
 $('#list-filter')?.addEventListener('change',event=>{state.filter=event.target.value;state.page=1;loadList().catch(e=>toast(e.message));});
}
let listRequest=0;
async function loadList() {
 const view=state.view,request=++listRequest;
 const params=new URLSearchParams({page:state.page,search:state.search});
 if(state.filter){const key={vaccines:'seguimiento',reminders:'estado',pets:'especie',fichas:'veterinario',availability:'veterinario'}[view];if(key)params.set(key,state.filter);}
 const data=await api(`/api/${endpoints[view]}/?${params}`);
 if(state.view!==view || request!==listRequest)return;
 state.list=data;
 $('#list-content').innerHTML=data.results.length?`<div class="table-wrap"><table><thead><tr>${configs[view].headers.map(h=>`<th>${h.toUpperCase()}</th>`).join('')}<th>ACCIONES</th></tr></thead><tbody>${data.results.map(row=>rowHTML(view,row)).join('')}</tbody></table></div><div class="list-controls"><span>${data.count} registros · Página ${state.page}</span><div>${data.previous?button('← Anterior','previous','','secondary'):''}${data.next?button('Siguiente →','next','','secondary'):''}</div></div>`:empty(state.search||state.filter?'No encontramos coincidencias.':'Todavía no hay registros.',state.search||state.filter?'Prueba con otra búsqueda o filtro.':'Usa el botón superior para registrar información.');
}
function rowHTML(view,r) {
 let cols=[];
 if(view==='tutors')cols=[`<strong>${esc(r.nombre_completo)}</strong><small>${esc(r.rut)}</small>`,`${esc(r.correo)}<small>${esc(r.telefono)}</small>`,esc(r.direccion),String((state.refs.mascotas||[]).filter(p=>p.tutor===r.id).length)];
 if(view==='pets')cols=[`<div class="pet-cell"><span class="pet-avatar">${icon('pets')}</span><div><strong>${esc(r.nombre)}</strong><small>${esc(r.especie)} · ${esc(r.raza||'Sin raza especificada')}</small></div></div>`,esc(r.tutor_nombre),fmt(r.fecha_nacimiento),`${esc(r.peso)} kg`];
 if(view==='vets')cols=[`<strong>${esc(r.nombre)}</strong>`,esc(r.usuario_nombre),esc(r.especialidad),statusBadge(r.activo?'Activo':'Inactivo')];
 if(view==='availability')cols=[esc(r.veterinario_nombre),esc(r.dia_nombre),hm(r.hora_inicio),hm(r.hora_termino)];
 if(view==='fichas')cols=[`<strong>${esc(r.mascota_nombre)}</strong>`,fmt(r.fecha_atencion),esc(r.veterinario_nombre),`<div class="record-summary">${esc(r.motivo)}</div>`];
 if(view==='vaccines')cols=[`<strong>${esc(r.nombre)}</strong><small>${esc(r.mascota_nombre)}</small>`,fmt(r.fecha_aplicacion),fmt(r.fecha_proxima_dosis),`<span class="badge ${r.seguimiento_cerrado?'info':r.vencida?'danger':r.fecha_proxima_dosis<=dateISO(new Date(Date.now()+7*86400000))?'warning':''}">${r.seguimiento_cerrado?'Cerrado':r.vencida?'Atrasada':'Próxima dosis'}</span>`];
 if(view==='reminders')cols=[esc(r.mascota_nombre),`${esc(r.tipo)}<small>${fmt(r.fecha_programada)}</small>`,`<div class="record-summary">${esc(r.mensaje)}</div>${r.error_envio?'<small class="error">Envío pendiente: revisar SMTP.</small>':r.correo_enviado?'<small>Correo enviado</small>':'<small>Sin envío de correo</small>'}`,statusBadge(r.estado)];
 if(view==='users')cols=[`<strong>${esc(r.username)}</strong>`,esc(`${r.first_name} ${r.last_name}`),esc(r.rol),statusBadge(r.is_active?'Activo':'Inactivo')];
 let actions=button('Ver','detail',r.id);
 const owns=!['fichas','vaccines','availability'].includes(view)||ownVet(r.veterinario);
 if(canWrite(view)&&owns)actions+=button('Editar','edit',r.id);
 if(view==='reminders'&&r.estado==='Pendiente')actions+=button('Atender','attend',r.id);
 if((isAdmin()&&view!=='users')||(['tutors','pets'].includes(view))||(view==='availability'&&owns&&isClinical()))actions+=button('Eliminar','delete',r.id,'text-button text-danger');
 return `<tr>${cols.map(c=>`<td>${c}</td>`).join('')}<td><div class="row-actions">${actions}</div></td></tr>`;
}
const option = (value,label,selected) => `<option value="${esc(value)}" ${String(value)===String(selected)?'selected':''}>${esc(label)}</option>`;
const field = (name,label,type='text',opts={}) => ({name,label,type,...opts});
function fieldsFor(view) {
 const tutors=(state.refs.tutores||[]).map(t=>[t.id,`${t.nombre_completo} · ${t.rut}`]);
 const pets=(state.refs.mascotas||[]).map(p=>[p.id,`${p.nombre} · ${p.tutor_nombre}`]);
 const vets=(state.refs.veterinarios||[]).filter(v=>v.activo&&(isAdmin()||!['fichas','vaccines','availability'].includes(view)||v.id===state.profile.veterinario)).map(v=>[v.id,v.nombre]);
 const pet=field('mascota','Mascota','select',{options:pets});
 const vet=field('veterinario','Profesional responsable','select',{options:vets});
 const obs=field('observaciones','Observaciones','textarea',{optional:true,wide:true,max:4000});
 if(view==='tutors')return [field('nombre','Nombre'),field('apellidos','Apellidos'),field('rut','RUT','text',{placeholder:'12.345.678-5'}),field('telefono','Teléfono','tel'),field('correo','Correo electrónico','email'),field('direccion','Dirección')];
 if(view==='pets')return [field('tutor','Tutor','select',{options:tutors}),field('nombre','Nombre'),field('especie','Especie','select',{options:['Perro','Gato','Ave','Conejo','Otro'].map(x=>[x,x])}),field('raza','Raza','text',{optional:true}),field('sexo','Sexo','select',{options:['Macho','Hembra','Sin especificar'].map(x=>[x,x])}),field('fecha_nacimiento','Fecha de nacimiento','date',{max:today()}),field('peso','Peso (kg)','number',{min:0.01,max:1000,step:'0.01'}),obs];
 if(view==='vets')return [field('usuario','Usuario de acceso','select',{options:(state.refs.usuarios||[]).filter(u=>u.rol==='Veterinario').map(u=>[u.id,u.username])}),field('nombre','Nombre profesional'),field('especialidad','Especialidad'),field('activo','Profesional activo','checkbox',{optional:true})];
 if(view==='availability')return [vet,field('dia_semana','Día de atención','select',{options:['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo'].map((d,i)=>[i,d])}),field('hora_inicio','Inicio','time'),field('hora_termino','Término','time')];
 if(view==='agenda')return [pet,vet,field('fecha','Fecha','date'),field('hora_inicio','Hora de inicio','time'),field('hora_termino','Hora de término','time'),field('estado','Estado','select',{options:['Pendiente','Confirmada','Completada','Cancelada'].map(x=>[x,x])}),field('motivo','Motivo de la cita','textarea',{wide:true,max:500})];
 if(view==='fichas')return [pet,vet,field('cita','Cita relacionada (opcional)','select',{options:[],optional:true}),field('fecha_atencion','Fecha de atención','date',{max:today()}),field('motivo','Motivo de consulta','text',{wide:true,max:500}),...['sintomas','diagnostico','tratamiento','receta_medica','examenes_solicitados','resultados','observaciones'].map((key,i)=>field(key,['Síntomas','Diagnóstico','Tratamiento','Receta médica / medicamentos','Exámenes solicitados','Resultados','Observaciones'][i],'textarea',{wide:true,optional:i>2,max:5000}))];
 if(view==='vaccines')return [pet,vet,field('nombre','Nombre de la vacuna'),field('fecha_aplicacion','Fecha de aplicación','date',{max:today()}),field('fecha_proxima_dosis','Próxima dosis','date'),field('seguimiento_cerrado','Seguimiento cerrado: próxima dosis realizada o resuelta','checkbox',{optional:true}),obs];
 if(view==='reminders')return [pet,field('tipo','Tipo','select',{options:[['Control','Control']]}),field('fecha_programada','Fecha programada','date'),field('estado','Estado','select',{options:[['Pendiente','Pendiente'],['Atendido','Atendido']]}),field('mensaje','Mensaje','textarea',{wide:true,max:4000})];
 if(view==='users')return [field('username','Usuario'),field('first_name','Nombre','text',{optional:true}),field('last_name','Apellidos','text',{optional:true}),field('email','Correo electrónico','email',{optional:true}),field('rol','Rol','select',{options:['Administrador','Veterinario','Recepcionista'].map(x=>[x,x])}),field('is_active','Cuenta activa','checkbox',{optional:true}),field('password','Contraseña (10 caracteres o más)','password',{optional:true,wide:true})];
 return [];
}
function fieldHTML(f,values) {
 const value=values[f.name] ?? (f.name==='veterinario'?state.profile.veterinario:'');
 const attr=`name="${f.name}" id="field-${f.name}" ${f.optional?'':'required'}`;
 let input;
 if(f.type==='select')input=`<select ${attr}>${f.optional?option('','Sin asociación',value):option('','Selecciona…',value)}${(f.options||[]).map(([v,l])=>option(v,l,value)).join('')}</select>`;
 else if(f.type==='textarea')input=`<textarea ${attr} maxlength="${f.max||4000}" rows="3">${esc(value)}</textarea>`;
 else if(f.type==='checkbox')input=`<input ${attr} type="checkbox" ${value?'checked':''}>`;
 else input=`<input ${attr} type="${f.type}" value="${esc(value)}" ${f.min!=null?`min="${f.min}"`:''} ${f.max!=null?`max="${f.max}"`:''} ${f.step?`step="${f.step}"`:''} ${f.placeholder?`placeholder="${esc(f.placeholder)}"`:''} ${f.type==='password'?'autocomplete="new-password"':'maxlength="500"'}>`;
 return `<label class="${f.wide?'span-2':''} ${f.type==='checkbox'?'field-checkbox':''}" for="field-${f.name}">${f.type==='checkbox'?input:''}${esc(f.label)}${f.type!=='checkbox'?input:''}</label>`;
}
async function openForm(view,id=null,prefill={}) {
 await loadRefs();
 let values=id?await api(`/api/${endpoints[view]}/${id}/`):{fecha:today(),fecha_atencion:today(),fecha_aplicacion:today(),estado:view==='agenda'?'Pendiente':'Pendiente',activo:true,is_active:true,...prefill};
 if(view==='agenda'&&id&&!futureSlot(values.fecha,hm(values.hora_inicio)))return appointmentDetail(id);
 let fields=fieldsFor(view);
 if(view==='agenda'&&!id)fields.find(f=>f.name==='fecha').min=today();
 if(view==='fichas'){
  const appointments=await all('citas');
  fields.find(f=>f.name==='cita').options=appointments.filter(a=>a.estado!=='Cancelada').map(a=>[a.id,`${a.mascota_nombre} · ${fmt(a.fecha)} ${hm(a.hora_inicio)} · ${a.veterinario_nombre}`]);
 }
 if(view==='reminders'&&values.vacuna)fields=fields.filter(f=>f.name==='estado');
 const title=id?`Editar ${labels[view].toLowerCase()}`:view==='agenda'?'Agendar una cita':configs[view]?.new;
 showModal(title,`<form id="entity-form"><div class="form-grid">${fields.map(f=>fieldHTML(f,values)).join('')}${view==='agenda'?'<div id="schedule-info" class="schedule-info"></div>':''}</div>${view==='vets'?'<p class="form-help">Crea primero un usuario con rol Veterinario en Usuarios.</p>':''}${view==='users'?'<p class="form-help">Al editar, deja la contraseña vacía para conservarla. Asocia un perfil profesional para activar un usuario veterinario.</p>':''}${view==='availability'?'<p class="form-help">Puedes crear varias franjas por día. Los cambios no pueden dejar citas futuras fuera de horario.</p>':''}<p class="error" id="form-error" role="alert"></p><div class="form-footer">${button('Volver','close','','secondary')}<button class="primary" type="submit">${id?'Guardar cambios':'Guardar registro'}</button></div></form>`);
 if(view==='agenda'){
  const info=()=>{
   const vet=Number($('#field-veterinario').value),d=$('#field-fecha').value;
   const weekday=d?(parseDate(d).getDay()+6)%7:null;
   const slots=(state.refs.disponibilidades||[]).filter(s=>s.veterinario===vet&&s.dia_semana===weekday);
   $('#schedule-info').textContent=!vet||!d?'Selecciona un profesional y una fecha para consultar su horario.':slots.length?`Horario disponible: ${slots.map(s=>`${hm(s.hora_inicio)} – ${hm(s.hora_termino)}`).join(' / ')}. Las citas ya reservadas se validan al guardar.`:'Este profesional no tiene disponibilidad en el día seleccionado.';
  };
  $('#field-veterinario').addEventListener('change',info);$('#field-fecha').addEventListener('change',info);info();
 }
 $('#entity-form').addEventListener('submit',async event=>{
  event.preventDefault();const submit=$('button[type=submit]',event.target);setBusy(submit,true);$('#form-error').textContent='';
  try {
   const fd=new FormData(event.target),data={};
   for(const f of fields){let value=f.type==='checkbox'?$('#field-'+f.name).checked:fd.get(f.name);if(f.type==='select'&&['tutor','mascota','veterinario','usuario','cita','dia_semana'].includes(f.name))value=value===''?null:Number(value);if(f.type==='password'&&!value)continue;data[f.name]=value;}
   await api(`/api/${endpoints[view]}/${id?`${id}/`:''}`,{method:id?'PATCH':'POST',body:JSON.stringify(data)});
   closeModal();toast(id?'Cambios guardados.':'Registro guardado correctamente.');await loadRefs();
   if(state.view===view || (view==='agenda'&&state.view==='dashboard')){if(state.view==='dashboard')await renderDashboard();else if(view==='agenda')await loadCalendar();else await loadList();}
  } catch(e){$('#form-error').textContent=e.message;setBusy(submit,false);}
 });
}
async function showDetail(view,id) {
 const data=await api(`/api/${endpoints[view]}/${id}/`);
 if(view==='pets'){
  const tutor=(state.refs.tutores||[]).find(t=>t.id===data.tutor);
  const fichas=isClinical()?await all('fichas',`mascota=${id}`):[];
  const vaccines=await all('vacunas',`mascota=${id}`);
  showModal(`Ficha de ${data.nombre}`,`<div class="detail-head"><strong>${esc(data.especie)} · ${esc(data.raza||'Raza no especificada')} · ${esc(data.sexo)}</strong><p>Nacimiento: ${fmt(data.fecha_nacimiento)} · Peso: ${esc(data.peso)} kg</p><p>Tutor: ${esc(data.tutor_nombre)} · ${esc(tutor?.telefono||'')}</p><p>${esc(data.observaciones)}</p></div><div class="actions">${isClinical()?`<a class="secondary" href="/mascotas/${id}/imprimir/" target="_blank" rel="noopener">Imprimir historial ↗</a>${button('+ Registrar atención','new-record',id,'primary')}`:''}</div><h3 class="section-title">Historial clínico</h3>${!isClinical()?'<p>Acceso reservado a veterinarios y administradores.</p>':fichas.length?`<div class="history-list">${fichas.map(f=>`<div class="clinical-entry"><small>${fmt(f.fecha_atencion)} · ${esc(f.veterinario_nombre)}</small><h3>${esc(f.motivo)}</h3><p>${esc(f.diagnostico)}</p>${button('Ver atención completa','detail-record',f.id)}</div>`).join('')}</div>`:empty('Sin atenciones registradas.','')}<h3>Vacunación</h3>${vaccines.map(v=>`<div class="item-row"><div><strong>${esc(v.nombre)}</strong><p>Aplicada ${fmt(v.fecha_aplicacion)} · Próxima dosis ${fmt(v.fecha_proxima_dosis)}</p></div><span class="badge ${v.vencida?'danger':''}">${v.seguimiento_cerrado?'Cerrado':v.vencida?'Atrasada':'Programada'}</span></div>`).join('')||empty('Sin vacunas registradas.','')}`);return;
 }
 if(view==='tutors'){
  const pets=await all('mascotas',`tutor=${id}`);
  showModal(data.nombre_completo,`<div class="detail-head"><p>RUT: ${esc(data.rut)}</p><p>${esc(data.correo)} · ${esc(data.telefono)}</p><p>${esc(data.direccion)}</p></div><h3>Mascotas a su cuidado</h3>${pets.map(p=>`<div class="item-row"><span class="pet-avatar">${icon('pets')}</span><div><strong>${esc(p.nombre)}</strong><p>${esc(p.especie)} · ${esc(p.raza)}</p></div>${button('Ver ficha','detail-pet',p.id)}</div>`).join('')||empty('Sin mascotas asociadas.','Puedes registrar varias mascotas para este tutor.')}`);return;
 }
 const labelsByKey={mascota_nombre:'Mascota',veterinario_nombre:'Profesional',usuario_nombre:'Usuario',dia_nombre:'Día',fecha_atencion:'Fecha de atención',motivo:'Motivo',sintomas:'Síntomas',diagnostico:'Diagnóstico',tratamiento:'Tratamiento',receta_medica:'Receta médica',examenes_solicitados:'Exámenes solicitados',resultados:'Resultados',observaciones:'Observaciones',nombre:'Nombre',fecha_aplicacion:'Aplicación',fecha_proxima_dosis:'Próxima dosis',especialidad:'Especialidad',activo:'Activo',hora_inicio:'Hora de inicio',hora_termino:'Hora de término',tipo:'Tipo',fecha_programada:'Fecha programada',mensaje:'Mensaje',estado:'Estado',correo_enviado:'Correo enviado',error_envio:'Estado del envío',username:'Usuario',first_name:'Nombre',last_name:'Apellidos',rol:'Rol',is_active:'Activo',email:'Correo',seguimiento_cerrado:'Seguimiento cerrado'};
 showModal(view==='fichas'?'Detalle de atención':labels[view],`<div class="detail-grid">${Object.entries(labelsByKey).filter(([key])=>data[key]!==undefined).map(([key,label])=>`<div><h4>${label}</h4><p>${esc(typeof data[key]==='boolean'?(data[key]?'Sí':'No'):data[key]||'—')}</p></div>`).join('')}</div>${view==='fichas'?`<div class="form-footer"><a href="/mascotas/${data.mascota}/imprimir/" class="secondary" target="_blank" rel="noopener">Imprimir historial ↗</a></div>`:''}`);
}
function renderCalendarShell() {
 $('#main').innerHTML=heading('Agenda médica','Una agenda compartida. Cada paciente en su momento.',button('+ Agendar cita','new-appointment','','primary'))+
 `<div class="toolbar"><div class="actions">${button('←','calendar-prev','','secondary')}${button('Hoy','calendar-today','','secondary')}${button('→','calendar-next','','secondary')}</div><strong id="calendar-title" class="date-title"></strong><div class="view-tabs" role="group" aria-label="Vista de calendario">${[['day','Día'],['week','Semana'],['month','Mes']].map(([mode,name])=>button(name,'calendar-mode',mode,mode===state.calendarMode?'selected':'')).join('')}</div><label>Profesional<select id="calendar-vet"><option value="">Todos</option>${(state.refs.veterinarios||[]).map(v=>option(v.id,v.nombre,state.calendarVet)).join('')}</select></label><label>Estado<select id="calendar-status">${['','Pendiente','Confirmada','Completada','Cancelada'].map(s=>option(s,s||'Todos',state.calendarStatus)).join('')}</select></label></div><section class="panel"><div id="calendar" class="calendar-scroll"></div><div class="legend"><span>Intervalos según duración real · Horario local de la clínica</span><span>Selecciona una cita para modificarla o cancelarla.</span></div></section>`;
 $('#calendar-vet').addEventListener('change',event=>{state.calendarVet=event.target.value;loadCalendar().catch(e=>toast(e.message));});
 $('#calendar-status').addEventListener('change',event=>{state.calendarStatus=event.target.value;loadCalendar().catch(e=>toast(e.message));});
}
function calendarRange() {
 let start=new Date(state.calendarDate),end=new Date(start);
 if(state.calendarMode==='month'){
  start=new Date(start.getFullYear(),start.getMonth(),1,12);start.setDate(start.getDate()-(start.getDay()+6)%7);end=new Date(start);end.setDate(end.getDate()+41);
 }else if(state.calendarMode==='week'){
  start.setDate(start.getDate()-(start.getDay()+6)%7);end=new Date(start);end.setDate(end.getDate()+6);
 }
 return [start,end];
}
let calendarRequest=0;
async function loadCalendar() {
 const request=++calendarRequest,[start,end]=calendarRange();
 const params=new URLSearchParams({desde:dateISO(start),hasta:dateISO(end)});
 if(state.calendarVet)params.set('veterinario',state.calendarVet);
 if(state.calendarStatus)params.set('estado',state.calendarStatus);
 const events=await all('citas',params.toString());
 if(state.view!=='agenda'||request!==calendarRequest)return;
 state.events=events;
 $('#calendar-title').textContent=state.calendarMode==='month'?state.calendarDate.toLocaleDateString('es-CL',{month:'long',year:'numeric'}):state.calendarMode==='day'?fmt(dateISO(start)):`${fmt(dateISO(start))} – ${fmt(dateISO(end))}`;
 document.querySelectorAll('[data-action="calendar-mode"]').forEach(b=>b.classList.toggle('selected',b.dataset.id===state.calendarMode));
 if(state.calendarMode==='day'){
  const rows=[];
  for(let hour=0;hour<24;hour++){
   const items=events.filter(e=>Number(e.hora_inicio.slice(0,2))===hour);
   if(hour<8&&!items.length||hour>19&&!items.length)continue;
   rows.push(`<div class="daily-hour">${String(hour).padStart(2,'0')}:00</div><div class="daily-items ${dateISO(start)<today()?'past':''}">${items.map(eventHTML).join('')||calendarAdd(dateISO(start),`${String(hour).padStart(2,'0')}:00`)}</div>`);
  }
  $('#calendar').innerHTML=`<div class="daily">${rows.join('')}</div>`;return;
 }
 const days=[];
 for(let d=new Date(start);d<=end;d.setDate(d.getDate()+1)){
  const iso=dateISO(d),items=events.filter(e=>e.fecha===iso),outside=d.getMonth()!==state.calendarDate.getMonth();
  days.push(`<div class="day ${iso===today()?'today':''} ${iso<today()?'past':''} ${state.calendarMode==='month'&&outside?'outside':''}"><div class="day-header"><span>${d.toLocaleDateString('es-CL',{weekday:'short'})}</span><b>${d.getDate()}</b></div>${items.map(eventHTML).join('')}${calendarAdd(iso)}</div>`);
 }
 $('#calendar').innerHTML=`<div class="${state.calendarMode==='month'?'month-grid':'week'}">${days.join('')}</div>`;
}
function eventHTML(a) {
 const cls=(a.veterinario%2===0?'purple ':'')+(a.estado==='Cancelada'?'cancelled':'');
 return `<button type="button" class="appointment ${cls}" data-action="edit-appointment" data-id="${a.id}"><span class="appt-time">${hm(a.hora_inicio)} – ${hm(a.hora_termino)}</span><strong>${esc(a.mascota_nombre)}</strong><small>${esc(a.veterinario_nombre)}</small><small>${esc(a.motivo)}</small>${statusBadge(a.estado)}</button>`;
}
async function appointmentDetail(id) {
 const a=await api(`/api/citas/${id}/`);
 const future=futureSlot(a.fecha,hm(a.hora_inicio));
 showModal(`Cita de ${a.mascota_nombre}`,`<div class="detail-head"><strong>${fmt(a.fecha)} · ${hm(a.hora_inicio)} – ${hm(a.hora_termino)}</strong><p>${esc(a.veterinario_nombre)} · ${esc(a.tutor_nombre)}</p>${statusBadge(a.estado)}</div><h3>Motivo</h3><p class="modal-text">${esc(a.motivo)}</p><div class="form-footer">${button('Ver paciente','detail-pet',a.mascota,'secondary')}${isClinical()&&a.ficha_id?button('Ver atención','detail-record',a.ficha_id,'primary'):isClinical()&&a.estado!=='Cancelada'?button('Registrar atención','appointment-record',id,'primary'):''}${future?button('Modificar cita','modify-appointment',id,'primary'):'<span class="subtle">Cita histórica: solo consulta</span>'}${future&&a.estado!=='Cancelada'?button('Cancelar cita','cancel-appointment',id,'danger-button'):''}${future&&isAdmin()?button('Eliminar','delete-appointment',id,'danger-button'):''}</div>`);
}
async function deleteRecord(view,id) {
 showModal('Eliminar registro',`<p>Esta acción elimina el registro permanentemente. Si contiene información relacionada, el sistema conservará el historial e impedirá la eliminación.</p><form id="delete-form"><p class="error" id="delete-error" role="alert"></p><div class="form-footer">${button('Volver','close','','secondary')}<button type="submit" class="danger-button">Confirmar eliminación</button></div></form>`);
 $('#delete-form').addEventListener('submit',async event=>{
  event.preventDefault();const submit=$('button[type=submit]',event.target);setBusy(submit,true);
  try{await api(`/api/${endpoints[view]}/${id}/`,{method:'DELETE',body:'{}'});closeModal();toast('Registro eliminado.');await loadRefs();if(state.view==='agenda')await loadCalendar();else if(state.view==='dashboard')await renderDashboard();else await loadList();}
  catch(e){$('#delete-error').textContent=e.message;setBusy(submit,false);}
 });
}
function renderProfile() {
 const p=state.profile;
 const fields=[field('first_name','Nombre','text',{optional:true}),field('last_name','Apellidos','text',{optional:true}),field('email','Correo electrónico','email',{optional:true}),field('current_password','Contraseña actual (para cambiarla)','password',{optional:true}),field('password','Nueva contraseña','password',{optional:true})];
 $('#main').innerHTML=heading('Mi perfil','Tu identidad y seguridad de acceso.')+`<section class="panel profile-panel"><div class="panel-body"><div class="profile-meta"><strong>${esc(p.username)}</strong><span class="badge">${esc(p.rol)}</span></div><form id="profile-form"><div class="form-grid">${fields.map(f=>fieldHTML(f,p)).join('')}</div><p class="form-help">Para cambiar la contraseña, completa ambos campos. Usa al menos 10 caracteres y evita contraseñas comunes.</p><p id="profile-error" role="alert" class="error"></p><button class="primary" type="submit">Guardar mi perfil</button></form></div></section>`;
 $('#profile-form').addEventListener('submit',async event=>{
  event.preventDefault();const submit=$('button[type=submit]',event.target);setBusy(submit,true);
  try{const data=Object.fromEntries(new FormData(event.target));if(!data.password){delete data.password;delete data.current_password;}state.profile=await api('/api/perfil/',{method:'PATCH',body:JSON.stringify(data)});toast('Perfil actualizado.');renderProfile();}
  catch(e){$('#profile-error').textContent=e.message;setBusy(submit,false);}
 });
}
document.addEventListener('click',async event=>{
 const nav=event.target.closest('[data-view]');if(nav){navigate(nav.dataset.view);return;}
 const b=event.target.closest('[data-action]');if(!b)return;
 const action=b.dataset.action,id=b.dataset.id;setBusy(b,true);
 try{
  if(action==='close')closeModal();
  else if(action.startsWith('go-'))await navigate(action.slice(3));
  else if(action==='new')await openForm(state.view);
  else if(action==='edit')await openForm(state.view,id);
  else if(action==='detail')await showDetail(state.view,id);
  else if(action==='detail-pet')await showDetail('pets',id);
  else if(action==='detail-record')await showDetail('fichas',id);
  else if(action==='appointment-record'){const a=await api(`/api/citas/${id}/`);await openForm('fichas',null,{mascota:a.mascota,veterinario:a.veterinario,cita:a.id,motivo:a.motivo});}
  else if(action==='new-record')await openForm('fichas',null,{mascota:Number(id)});
  else if(action==='delete')await deleteRecord(state.view,id);
  else if(action==='delete-appointment')await deleteRecord('agenda',id);
  else if(action==='new-appointment')await openForm('agenda');
  else if(action==='edit-appointment')await appointmentDetail(id);
  else if(action==='modify-appointment')await openForm('agenda',id);
  else if(action==='cancel-appointment'){
   await api(`/api/citas/${id}/cancelar/`,{method:'POST',body:'{}'});closeModal();toast('Cita cancelada. El horario quedó disponible.');await refresh();
  }else if(action==='attend'){
   await api(`/api/recordatorios/${id}/atender/`,{method:'POST',body:'{}'});toast('Recordatorio marcado como atendido.');await loadList();
  }else if(action==='previous'||action==='next'){state.page+=action==='next'?1:-1;await loadList();}
  else if(action==='calendar-mode'){state.calendarMode=id;await loadCalendar();}
  else if(action==='calendar-today'){state.calendarDate=parseDate(today());await loadCalendar();}
  else if(action==='calendar-next'||action==='calendar-prev'){
   const direction=action==='calendar-next'?1:-1;
   if(state.calendarMode==='month')state.calendarDate=new Date(state.calendarDate.getFullYear(),state.calendarDate.getMonth()+direction,1,12);
   else state.calendarDate.setDate(state.calendarDate.getDate()+direction*(state.calendarMode==='week'?7:1));
   await loadCalendar();
  }else if(action==='calendar-add'){
   const [fecha,hora_inicio]=id.split('|');
   if(fecha<today()||(hora_inicio&&!futureSlot(fecha,hora_inicio)))throw new Error('Selecciona una fecha y hora futuras.');
   if(!hora_inicio){await openForm('agenda',null,{fecha,...(state.calendarVet?{veterinario:Number(state.calendarVet)}:{})});return;}
   const [hour,minute]=hora_inicio.split(':').map(Number);
   const end=new Date(`${fecha}T${hora_inicio}:00`);end.setMinutes(minute+30);
   await openForm('agenda',null,{fecha,hora_inicio,hora_termino:`${String(end.getHours()).padStart(2,'0')}:${String(end.getMinutes()).padStart(2,'0')}`,...(state.calendarVet?{veterinario:Number(state.calendarVet)}:{})});
  }
 }catch(e){toast(e.message);}finally{setBusy(b,false);}
});
$('#close-modal').addEventListener('click',closeModal);
async function boot() {
 try{
  state.profile=await api('/api/perfil/');
  state.calendarDate=parseDate(state.profile.hoy);
  document.querySelectorAll('[data-admin]').forEach(e=>e.hidden=!isAdmin());
  document.querySelectorAll('[data-clinical]').forEach(e=>e.hidden=!isClinical());
  document.querySelectorAll('#nav button').forEach(b=>{b.innerHTML=icon(b.dataset.view)+`<span>${labels[b.dataset.view]}</span>`;});
  await loadRefs();await navigate('dashboard');$('#sync').textContent='● Actualizado';setInterval(refresh,15000);
 }catch(e){$('#main').innerHTML=empty('No se pudo iniciar el espacio de trabajo.',e.message);toast(e.message);}
}
boot();
