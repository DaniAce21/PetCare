#!/usr/bin/env python3
"""PetCare: aplicación local sin dependencias de terceros. Python >= 3.11."""
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import smtplib
import sqlite3
import ssl
import threading
import time
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv('PETCARE_DB', str(ROOT / 'data' / 'petcare.db')))
SESSIONS = {}
SESSION_LOCK = threading.Lock()
LOGIN_ATTEMPTS = {}
STATUSES = {'Confirmada', 'En atención', 'Completada', 'Cancelada'}

class ValidationError(Exception):
    pass

def connect():
    db = sqlite3.connect(DB_PATH, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 310000).hex()
    return salt + ':' + digest

def verify_password(password, stored):
    return hmac.compare_digest(password_hash(password, stored.split(':')[0]), stored)

def required(data, field, max_length=200):
    val = str(data.get(field, '')).strip()
    if not val or len(val) > max_length:
        raise ValidationError(f'{field}: completa el campo (máximo {max_length} caracteres).')
    return val

def ident(data, field):
    try:
        value = int(data.get(field, 0))
    except (ValueError, TypeError):
        raise ValidationError(f'{field}: identificador inválido.')
    if value <= 0:
        raise ValidationError(f'{field}: selecciona una opción válida.')
    return value

def iso_date(value):
    try:
        return date.fromisoformat(str(value)).isoformat()
    except (ValueError, TypeError):
        raise ValidationError('Fecha inválida. Usa AAAA-MM-DD.')

def iso_datetime(value):
    try:
        dt = datetime.fromisoformat(str(value))
        if dt.tzinfo or dt.second or dt.microsecond:
            raise ValueError()
        return dt
    except (ValueError, TypeError):
        raise ValidationError('Fecha y hora inválidas. Usa la hora local de la clínica, sin segundos.')

def validate_appointment(db, data, appointment_id=0):
    pet_id, vet_id = ident(data, 'pet_id'), ident(data, 'vet_id')
    start, end = iso_datetime(data.get('start')), iso_datetime(data.get('end'))
    status = data.get('status', 'Confirmada')
    if status not in STATUSES:
        raise ValidationError('Estado de cita inválido.')
    if end <= start or end.date() != start.date() or end - start > timedelta(hours=4):
        raise ValidationError('La cita debe durar entre 1 minuto y 4 horas dentro del mismo día.')
    if not db.execute('SELECT id FROM pets WHERE id=?', (pet_id,)).fetchone():
        raise ValidationError('La mascota no existe.')
    if not db.execute('SELECT id FROM vets WHERE id=? AND active=1', (vet_id,)).fetchone():
        raise ValidationError('El profesional no está disponible.')
    start_s, end_s = start.isoformat(timespec='minutes'), end.isoformat(timespec='minutes')
    if status != 'Cancelada':
        schedule = db.execute('SELECT * FROM availability WHERE vet_id=? AND weekday=?', (vet_id, start.weekday())).fetchall()
        if not any(row['start_time'] <= start.strftime('%H:%M') and end.strftime('%H:%M') <= row['end_time'] for row in schedule):
            raise ValidationError('La cita queda fuera de la disponibilidad del profesional.')
        conflict = db.execute("SELECT id FROM appointments WHERE id<>? AND status<>'Cancelada' AND (vet_id=? OR pet_id=?) AND start<? AND end>?", (appointment_id, vet_id, pet_id, end_s, start_s)).fetchone()
        if conflict:
            raise ValidationError('Horario ocupado: el profesional o la mascota ya tiene una cita en ese intervalo.')
    return pet_id, vet_id, start_s, end_s, required(data, 'reason', 500), status

def save_entity(db, entity, data, entity_id=None):
    # Serializa la comprobación y escritura: dos clientes no pueden reservar el mismo horario.
    db.execute('BEGIN IMMEDIATE')
    if entity_id and not db.execute(f'SELECT id FROM {entity} WHERE id=?', (entity_id,)).fetchone():
        raise ValidationError('El registro ya no existe.')
    if entity == 'tutors':
        email = required(data, 'email')
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
            raise ValidationError('Ingresa un correo electrónico válido.')
        fields = ['name', 'email', 'phone', 'address']
        values = [required(data, 'name'), email, required(data, 'phone', 40), str(data.get('address', ''))[:500]]
    elif entity == 'pets':
        birth = iso_date(data['birth_date']) if data.get('birth_date') else None
        if birth and birth > date.today().isoformat():
            raise ValidationError('La fecha de nacimiento no puede ser futura.')
        species = required(data, 'species')
        if species not in ('Perro', 'Gato', 'Ave', 'Conejo', 'Otro'):
            raise ValidationError('Especie inválida.')
        fields = ['tutor_id', 'name', 'species', 'breed', 'birth_date', 'sex', 'allergies']
        values = [ident(data, 'tutor_id'), required(data, 'name'), species, str(data.get('breed', ''))[:200], birth, str(data.get('sex', 'Sin especificar'))[:50], str(data.get('allergies', ''))[:1000]]
    elif entity == 'vets':
        fields = ['name', 'specialty', 'color']
        color = str(data.get('color', '#147d70'))
        if not re.fullmatch('#[0-9a-fA-F]{6}', color):
            raise ValidationError('Color inválido.')
        values = [required(data, 'name'), required(data, 'specialty'), color]
    elif entity == 'appointments':
        fields = ['pet_id', 'vet_id', 'start', 'end', 'reason', 'status']
        values = validate_appointment(db, data, entity_id or 0)
    elif entity == 'records':
        if entity_id:
            raise ValidationError('Las fichas son registros históricos y no se sobrescriben. Agrega una nueva evolución.')
        weight = data.get('weight')
        try:
            weight = float(weight) if weight not in (None, '') else None
            if weight is not None and not (0 < weight <= 1000):
                raise ValueError()
        except (ValueError, TypeError):
            raise ValidationError('El peso debe ser un número mayor que cero y menor o igual a 1000 kg.')
        when = iso_date(data.get('date'))
        if when > date.today().isoformat():
            raise ValidationError('La atención clínica no puede tener fecha futura.')
        fields = ['pet_id', 'vet_id', 'date', 'weight', 'symptoms', 'diagnosis', 'treatment', 'notes']
        values = [ident(data, 'pet_id'), ident(data, 'vet_id'), when, weight, required(data, 'symptoms', 4000), required(data, 'diagnosis', 4000), required(data, 'treatment', 4000), str(data.get('notes', ''))[:4000]]
    elif entity == 'vaccinations':
        fields = ['pet_id', 'name', 'applied_date', 'due_date']
        applied, due = iso_date(data.get('applied_date')), iso_date(data.get('due_date'))
        if applied > date.today().isoformat() or due < applied:
            raise ValidationError('La aplicación no puede ser futura y el refuerzo debe ser posterior o igual a la aplicación.')
        values = [ident(data, 'pet_id'), required(data, 'name'), applied, due]
    else:
        raise ValidationError('Recurso inválido.')
    if entity_id:
        db.execute(f'UPDATE {entity} SET ' + ','.join(f'{f}=?' for f in fields) + ' WHERE id=?', [*values, entity_id])
    else:
        cur = db.execute(f'INSERT INTO {entity} ({",".join(fields)}) VALUES ({",".join("?" for _ in fields)})', values)
        entity_id = cur.lastrowid
    db.commit()
    return entity_id

def save_availability(db, vet_id, slots):
    if not isinstance(slots, list) or len(slots) > 28:
        raise ValidationError('Disponibilidad inválida.')
    normalized = []
    for slot in slots:
        try:
            weekday = int(slot['weekday'])
            start, end = slot['start_time'], slot['end_time']
            if weekday not in range(7) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', start) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', end) or start >= end:
                raise ValueError()
        except (KeyError, ValueError, TypeError):
            raise ValidationError('Revisa los días y las horas de disponibilidad.')
        if any(d == weekday and start < e and end > s for d, s, e in normalized):
            raise ValidationError('Las franjas de disponibilidad se superponen.')
        normalized.append((weekday, start, end))
    db.execute('BEGIN IMMEDIATE')
    if not db.execute('SELECT id FROM vets WHERE id=?', (vet_id,)).fetchone():
        raise ValidationError('El profesional no existe.')
    future = db.execute("SELECT start,end FROM appointments WHERE vet_id=? AND status IN ('Confirmada','En atención') AND end>=?", (vet_id, datetime.now().isoformat(timespec='minutes'))).fetchall()
    for appt in future:
        dt = datetime.fromisoformat(appt['start'])
        if not any(d == dt.weekday() and s <= appt['start'][11:] and e >= appt['end'][11:] for d, s, e in normalized):
            raise ValidationError('Hay citas futuras fuera del nuevo horario. Reprograma o cancela esas citas primero.')
    db.execute('DELETE FROM availability WHERE vet_id=?', (vet_id,))
    db.executemany('INSERT INTO availability(vet_id,weekday,start_time,end_time) VALUES(?,?,?,?)', [(vet_id, *slot) for slot in normalized])
    db.commit()

def generate_reminders(db, today=None):
    today = today or date.today()
    rows = db.execute('SELECT v.*,p.name AS pet_name,t.email,t.name AS tutor_name FROM vaccinations v JOIN pets p ON p.id=v.pet_id JOIN tutors t ON t.id=p.tutor_id WHERE v.due_date<=?', ((today + timedelta(days=7)).isoformat(),)).fetchall()
    for row in rows:
        subject = f"PetCare · Refuerzo de {row['name']} para {row['pet_name']}"
        body = f"Hola {row['tutor_name']}, el refuerzo de {row['name']} de {row['pet_name']} está programado para el {row['due_date']}. Comunícate con la clínica para reservar una cita. Equipo PetCare."
        db.execute("INSERT INTO reminders(vaccine_id,due_date,email,subject,body) VALUES(?,?,?,?,?) ON CONFLICT(vaccine_id) DO UPDATE SET due_date=excluded.due_date,email=excluded.email,subject=excluded.subject,body=excluded.body,status=CASE WHEN reminders.due_date<>excluded.due_date THEN 'Pendiente' ELSE reminders.status END,sent_at=CASE WHEN reminders.due_date<>excluded.due_date THEN NULL ELSE reminders.sent_at END", (row['id'], row['due_date'], row['email'], subject, body))
    # Un cambio del refuerzo a una fecha lejana elimina solamente avisos aún no enviados.
    db.execute("DELETE FROM reminders WHERE status='Pendiente' AND vaccine_id IN (SELECT id FROM vaccinations WHERE due_date>?)", ((today + timedelta(days=7)).isoformat(),))
    db.commit()

def send_pending(db):
    host = os.getenv('SMTP_HOST')
    if not host:
        return
    for row in db.execute("SELECT * FROM reminders WHERE status='Pendiente'").fetchall():
        try:
            msg = EmailMessage()
            msg['From'] = os.environ['SMTP_FROM']
            msg['To'], msg['Subject'] = row['email'], row['subject']
            msg.set_content(row['body'])
            with smtplib.SMTP(host, int(os.getenv('SMTP_PORT', '587')), timeout=15) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                if os.getenv('SMTP_USER'):
                    smtp.login(os.environ['SMTP_USER'], os.environ['SMTP_PASSWORD'])
                smtp.send_message(msg)
            db.execute("UPDATE reminders SET status='Enviado',sent_at=?,last_error=NULL WHERE id=?", (datetime.now().isoformat(timespec='seconds'), row['id']))
        except Exception as exc:
            db.execute('UPDATE reminders SET last_error=? WHERE id=?', (type(exc).__name__ + ': revisa la configuración SMTP y la conexión.', row['id']))
        db.commit()

def reminder_worker():
    while True:
        try:
            with connect() as db:
                generate_reminders(db)
                send_pending(db)
        except Exception as exc:
            print('Recordatorios:', type(exc).__name__, flush=True)
        time.sleep(60)

def init_db(demo=False):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript((ROOT / 'schema.sql').read_text())
        if not db.execute('SELECT id FROM users LIMIT 1').fetchone():
            password = os.getenv('PETCARE_ADMIN_PASSWORD') or secrets.token_urlsafe(12)
            if len(password) < 10:
                raise ValueError('PETCARE_ADMIN_PASSWORD debe tener al menos 10 caracteres.')
            db.execute('INSERT INTO users(username,password_hash) VALUES(?,?)', ('admin', password_hash(password)))
            print(f'Acceso inicial — usuario: admin | contraseña: {password}', flush=True)
        if demo and not db.execute('SELECT id FROM tutors LIMIT 1').fetchone():
            db.executemany('INSERT INTO tutors(name,email,phone,address) VALUES(?,?,?,?)', [('Camila Torres','camila@example.com','+56 9 5555 0101','Providencia, Santiago'),('Martín Rojas','martin@example.com','+56 9 5555 0102','Ñuñoa, Santiago'),('Valentina Soto','vale@example.com','+56 9 5555 0103','La Reina, Santiago')])
            db.executemany('INSERT INTO pets(tutor_id,name,species,breed,birth_date,sex,allergies) VALUES(?,?,?,?,?,?,?)', [(1,'Luna','Perro','Golden retriever','2021-05-12','Hembra','Sin alergias conocidas'),(2,'Simón','Gato','Europeo','2023-02-03','Macho',''),(3,'Milo','Perro','Mestizo','2022-08-14','Macho','')])
            db.executemany('INSERT INTO vets(name,specialty,color) VALUES(?,?,?)', [('Dra. Antonia Silva','Medicina general','#147d70'),('Dr. Nicolás Pérez','Medicina felina','#6574c4')])
            db.executemany('INSERT INTO availability(vet_id,weekday,start_time,end_time) VALUES(?,?,?,?)', [(v,d,'09:00','18:00') for v in (1,2) for d in range(5)])
            day = date.today()
            while day.weekday() > 4:
                day += timedelta(days=1)
            db.executemany('INSERT INTO appointments(pet_id,vet_id,start,end,reason) VALUES(?,?,?,?,?)', [(1,1,f'{day}T09:00',f'{day}T09:30','Control preventivo'),(2,2,f'{day}T10:00',f'{day}T10:45','Consulta general'),(3,1,f'{day}T11:00',f'{day}T11:30','Control de vacunación')])
            db.execute('INSERT INTO records(pet_id,vet_id,date,weight,symptoms,diagnosis,treatment,notes) VALUES(1,1,?,27.5,?,?,?,?,?)'.replace(',?,?,?,?,?)', ',?,?,?,?)'), ((date.today()-timedelta(days=30)).isoformat(),'Control preventivo anual','Paciente clínicamente estable','Mantener alimentación y actividad habitual','Datos ficticios para demostración.'))
            db.execute('INSERT INTO vaccinations(pet_id,name,applied_date,due_date) VALUES(1,?,?,?)', ('Refuerzo anual (demostración)',(date.today()-timedelta(days=360)).isoformat(),(date.today()+timedelta(days=5)).isoformat()))
        db.commit()

class Handler(BaseHTTPRequestHandler):
    server_version = 'PetCare'

    def log_message(self, fmt, *args):
        # No registrar cuerpos de peticiones ni credenciales.
        print(f'{self.address_string()} {fmt % args}', flush=True)

    def respond(self, data, status=200, cookie=None):
        payload = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def body(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 1 or length > 100000:
                raise ValueError()
            result = json.loads(self.rfile.read(length))
            if not isinstance(result, dict):
                raise ValueError()
            return result
        except (ValueError, json.JSONDecodeError):
            raise ValidationError('Solicitud JSON inválida o demasiado grande.')

    def session(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
            token = cookie['petcare_session'].value if 'petcare_session' in cookie else ''
        except Exception:
            return None
        with SESSION_LOCK:
            session = SESSIONS.get(token)
            if session and session['expires'] > time.time():
                return session
            SESSIONS.pop(token, None)
        return None

    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith('/api/'):
            session = self.session()
            if not session:
                return self.respond({'error':'Inicia sesión para continuar.'}, 401)
            if path == '/api/session':
                return self.respond({'username':session['username'], 'csrf':session['csrf']})
            if path == '/api/state':
                with connect() as db:
                    generate_reminders(db)
                    data = {table:[dict(r) for r in db.execute(f'SELECT * FROM {table} ORDER BY id')] for table in ('tutors','pets','vets','availability','appointments','records','vaccinations','reminders')}
                data['smtp_configured'] = bool(os.getenv('SMTP_HOST'))
                data['today'] = date.today().isoformat()
                return self.respond(data)
            return self.respond({'error':'Ruta no encontrada.'},404)
        files = {'/':'index.html','/app.js':'app.js','/style.css':'style.css'}
        if path not in files:
            return self.respond({'error':'Página no encontrada.'},404)
        file = ROOT / 'static' / files[path]
        payload = file.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', {'html':'text/html; charset=utf-8','js':'text/javascript; charset=utf-8','css':'text/css; charset=utf-8'}[file.suffix[1:]])
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Length',str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        self.mutate()

    def do_PUT(self):
        self.mutate()

    def mutate(self):
        path = urlparse(self.path).path
        try:
            data = self.body()
            if path == '/api/login' and self.command == 'POST':
                username, password = required(data,'username'), required(data,'password', 1000)
                key = self.client_address[0]
                now = time.time()
                with SESSION_LOCK:
                    attempts = [t for t in LOGIN_ATTEMPTS.get(key, []) if now-t < 300]
                    if len(attempts) >= 10:
                        return self.respond({'error':'Demasiados intentos. Espera 5 minutos.'},429)
                    LOGIN_ATTEMPTS[key] = attempts + [now]
                with connect() as db:
                    user = db.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
                if not user or not verify_password(password,user['password_hash']):
                    return self.respond({'error':'Usuario o contraseña incorrectos.'},401)
                token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
                with SESSION_LOCK:
                    for expired in [k for k,v in SESSIONS.items() if v['expires'] <= now]:
                        SESSIONS.pop(expired, None)
                    SESSIONS[token] = {'username':username,'csrf':csrf,'expires':now+8*3600}
                    LOGIN_ATTEMPTS.pop(key,None)
                return self.respond({'username':username,'csrf':csrf},cookie=f'petcare_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800')
            session = self.session()
            if not session:
                return self.respond({'error':'Tu sesión expiró. Inicia sesión nuevamente.'},401)
            if not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),session['csrf']):
                return self.respond({'error':'Solicitud no autorizada. Recarga la página.'},403)
            if path == '/api/logout':
                with SESSION_LOCK:
                    for key in [k for k,v in SESSIONS.items() if v is session]:
                        SESSIONS.pop(key,None)
                return self.respond({'ok':True},cookie='petcare_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
            match = re.fullmatch(r'/api/(tutors|pets|vets|appointments|records|vaccinations)(?:/(\d+))?',path)
            with connect() as db:
                if match:
                    entity, entity_id = match.groups()
                    if (self.command == 'POST' and entity_id) or (self.command == 'PUT' and not entity_id):
                        return self.respond({'error':'Método inválido.'},405)
                    result = save_entity(db,entity,data,int(entity_id) if entity_id else None)
                    generate_reminders(db)
                    return self.respond({'id':result},200 if entity_id else 201)
                match = re.fullmatch(r'/api/vets/(\d+)/availability',path)
                if match and self.command == 'PUT':
                    save_availability(db,int(match[1]),data.get('slots'))
                    return self.respond({'ok':True})
            return self.respond({'error':'Ruta no encontrada.'},404)
        except ValidationError as exc:
            self.respond({'error':str(exc)},400)
        except sqlite3.IntegrityError:
            self.respond({'error':'Los datos relacionados no existen o incumplen una regla de integridad.'},400)
        except sqlite3.OperationalError:
            self.respond({'error':'Base de datos ocupada. Intenta nuevamente.'},503)
        except Exception as exc:
            print('Error interno:',type(exc).__name__,flush=True)
            self.respond({'error':'Error interno del servidor.'},500)

def main():
    parser = argparse.ArgumentParser(description='Sistema de gestión veterinaria PetCare')
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--demo',action='store_true',help='Carga datos ficticios si la base está vacía')
    args = parser.parse_args()
    init_db(args.demo)
    threading.Thread(target=reminder_worker,daemon=True).start()
    server = ThreadingHTTPServer((args.host,args.port),Handler)
    print(f'PetCare disponible en http://{args.host}:{args.port} · hora local del servidor',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nPetCare detenido.')
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
