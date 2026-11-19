from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime, timezone
import json, sqlite3, asyncio, hashlib, hmac, secrets
from datetime import date
from fastapi import Header, HTTPException

ROOT=Path(__file__).resolve().parent.parent
DB=ROOT/'msrtc.db'
app=FastAPI(title='MSRTC SmartTrack API', version='1.0')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])



class LoginRequest(BaseModel):
    email: str
    password: str
    role: str

DEMO_USERS = {
    "passenger": {"email": "passenger@msrtc.com", "password": "passenger123", "name": "MSRTC Passenger"},
    "driver": {"email": "driver@msrtc.com", "password": "driver123", "name": "MSRTC Driver"},
    "admin": {"email": "admin@msrtc.com", "password": "admin123", "name": "MSRTC Admin"},
}

class Registration(BaseModel):
    email: str
    password: str
    name: str
    date_of_birth: date
    gender: str
    concession_card: bool = False

class ProfileUpdate(BaseModel):
    name: str
    date_of_birth: date
    gender: str
    concession_card: bool = False

def safe_profile(row):
    return {'name':row['name'],'email':row['email'],'date_of_birth':row['dob'], 'gender':row['gender'], 'concession_card':bool(row['card']), 'role':'passenger'}

def current_profile(authorization: str = Header(default='')):
    token=authorization.removeprefix('Bearer ').strip()
    if not token: raise HTTPException(401,'Please log in')
    with db() as c:
        row=c.execute('SELECT u.* FROM passenger_sessions s JOIN passenger_users u ON u.email=s.email WHERE s.token=?',(token,)).fetchone()
    if not row: raise HTTPException(401,'Session expired; log in again')
    return safe_profile(row)

@app.post('/api/register')
def register(payload:Registration):
    email=payload.email.strip().lower()
    if '@' not in email or len(email)>150: raise HTTPException(400,'Enter a valid email')
    if len(payload.password)<8: raise HTTPException(400,'Password must contain at least 8 characters')
    if not payload.name.strip() or len(payload.name)>100: raise HTTPException(400,'Enter a valid name')
    if payload.gender not in ('male','female','other','undisclosed'): raise HTTPException(400,'Invalid gender')
    if not date(1900,1,1)<=payload.date_of_birth<=date.today(): raise HTTPException(400,'Invalid date of birth')
    salt=secrets.token_hex(16)
    digest=hashlib.pbkdf2_hmac('sha256',payload.password.encode(),bytes.fromhex(salt),200000).hex()
    try:
        with db() as c:
            c.execute('INSERT INTO passenger_users VALUES (?,?,?,?,?,?,?)',(email,payload.name.strip(),str(payload.date_of_birth),payload.gender,int(payload.concession_card),salt,digest))
    except sqlite3.IntegrityError: raise HTTPException(409,'This email is already registered')
    return {'success':True,'message':'Account created. Please log in.'}

@app.get('/api/profile')
def get_profile(authorization: str = Header(default='')):
    return current_profile(authorization)

@app.put('/api/profile')
def update_profile(payload:ProfileUpdate,authorization: str = Header(default='')):
    profile=current_profile(authorization)
    if not payload.name.strip() or len(payload.name)>100 or payload.gender not in ('male','female','other','undisclosed') or not date(1900,1,1)<=payload.date_of_birth<=date.today():
        raise HTTPException(400,'Invalid profile details')
    with db() as c:
        c.execute('UPDATE passenger_users SET name=?,dob=?,gender=?,card=? WHERE email=?',(payload.name.strip(),str(payload.date_of_birth),payload.gender,int(payload.concession_card),profile['email']))
    return get_profile(authorization)

class Location(BaseModel):
    bus_id:str
    latitude:float
    longitude:float
    speed:float=0
    eta:int=0
    status:str='ON_TIME'
    current_stop:str='En route'

def db():
    con=sqlite3.connect(DB)
    con.row_factory=sqlite3.Row
    return con

def init_db():
    con=db(); con.execute('''CREATE TABLE IF NOT EXISTS locations(bus_id TEXT PRIMARY KEY,latitude REAL,longitude REAL,speed REAL,eta INTEGER,status TEXT,current_stop TEXT,updated_at TEXT)'''); con.commit(); con.close()
init_db()
with db() as c:
    c.execute('CREATE TABLE IF NOT EXISTS passenger_users(email TEXT PRIMARY KEY,name TEXT NOT NULL,dob TEXT NOT NULL,gender TEXT NOT NULL,card INTEGER NOT NULL,salt TEXT NOT NULL,password_hash TEXT NOT NULL)')
    c.execute('CREATE TABLE IF NOT EXISTS passenger_sessions(token TEXT PRIMARY KEY,email TEXT NOT NULL)')

@app.post('/api/login')
def login(payload: LoginRequest):
    role = payload.role.lower()
    if role=='passenger':
        with db() as c:
            record=c.execute('SELECT * FROM passenger_users WHERE email=?',(payload.email.strip().lower(),)).fetchone()
            if record:
                digest=hashlib.pbkdf2_hmac('sha256',payload.password.encode(),bytes.fromhex(record['salt']),200000).hex()
                if not hmac.compare_digest(digest,record['password_hash']): return {'success':False,'message':'Invalid email or password'}
                token=secrets.token_urlsafe(32)
                c.execute('INSERT INTO passenger_sessions VALUES (?,?)',(token,record['email']))
                return {'success':True,'role':'passenger','name':record['name'],'token':token,'profile':safe_profile(record)}
    user = DEMO_USERS.get(role)
    if not user or payload.email.lower() != user['email'] or payload.password != user['password']:
        return {"success": False, "message": "Invalid email, password or role"}
    return {"success": True, "role": role, "name": user["name"], "message": "Login successful"}

@app.get('/api/health')
def health(): return {'status':'running','service':'MSRTC SmartTrack'}

@app.get('/api/buses')
def buses(): return json.loads((ROOT/'data/buses.json').read_text())

@app.get('/api/routes')
def routes(): return json.loads((ROOT/'data/routes.json').read_text())

@app.get('/api/location/{bus_id}')
def location_get(bus_id:str):
    con=db(); row=con.execute('SELECT * FROM locations WHERE bus_id=?',(bus_id,)).fetchone(); con.close()
    return dict(row) if row else {'bus_id':bus_id,'status':'WAITING_FOR_GPS'}

@app.post('/api/location')
async def location_post(payload:Location):
    data=payload.model_dump(); data['updated_at']=datetime.now(timezone.utc).isoformat()
    con = db()
    con.execute('''
        INSERT OR REPLACE INTO locations
        (bus_id, latitude, longitude, speed, eta, status, current_stop, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['bus_id'], data['latitude'], data['longitude'], data['speed'],
        data['eta'], data['status'], data['current_stop'], data['updated_at']
    ))
    con.commit()
    con.close()
    await broadcast(data)
    return {'received':True,'data':data}

clients=[]
async def broadcast(data):
    dead=[]
    for ws in clients:
        try: await ws.send_json(data)
        except: dead.append(ws)
    for ws in dead:
        if ws in clients: clients.remove(ws)

@app.websocket('/ws/live/{bus_id}')
async def websocket_live(ws:WebSocket,bus_id:str):
    await ws.accept(); clients.append(ws)
    try:
        current=location_get(bus_id); await ws.send_json(current)
        while True: await asyncio.sleep(30)
    except WebSocketDisconnect:
        if ws in clients: clients.remove(ws)

app.mount('/data', StaticFiles(directory=ROOT/'data'), name='data')
app.mount('/dashboard', StaticFiles(directory=ROOT/'dashboard', html=True), name='dashboard')
app.mount('/driver', StaticFiles(directory=ROOT/'driver_app', html=True), name='driver')

@app.get('/login')
def login_page(): return FileResponse(ROOT/'passenger_app/login.html')

@app.get('/')
def passenger(): return FileResponse(ROOT/'passenger_app/index.html')

# Explore-map API. Coordinates are configured reference locations; not verified MSRTC stops.
@app.get('/api/map/nearby')
def map_nearby(south:float=-90, west:float=-180, north:float=90, east:float=180):
    def inside(lat,lon):
        return south <= lat <= north and (west <= lon <= east if west <= east else (lon >= west or lon <= east))
    cities=json.loads((ROOT/'data/cities.json').read_text(encoding='utf-8'))
    buses=json.loads((ROOT/'data/buses.json').read_text(encoding='utf-8'))
    con=db(); locations={r['bus_id']:dict(r) for r in con.execute('SELECT * FROM locations')};con.close()
    found=[]
    for bus in buses:
        loc=locations.get(bus['bus_id'])
        coords=cities.get(bus.get('from'))
        if loc:
            lat,lon=loc['latitude'],loc['longitude']; source='simulated GPS update'
        elif coords:
            lat,lon=coords;source='demo origin location'
        else: continue
        if inside(lat,lon):
            found.append({**bus,'latitude':lat,'longitude':lon,'source':source,'current_stop':loc.get('current_stop') if loc else bus.get('from'),'eta':loc.get('eta') if loc else None})
    stops=[{'id':f'REF-{i+1:03}', 'name':name,'latitude':xy[0],'longitude':xy[1], 'type':'reference location (not verified bus stop)'} for i,(name,xy) in enumerate(cities.items()) if inside(xy[0],xy[1])]
    return {'buses':found,'stops':stops,'notice':'Demo data only; reference locations are not verified MSRTC stops. Bus positions are simulated or demo origins.'}

@app.get('/explore')
def explore_map(): return FileResponse(ROOT/'passenger_app/explore.html')

# Educational family-booking module (separate from official MSRTC systems)
from backend.booking import router as booking_router, configure as configure_booking
configure_booking(DB)
app.include_router(booking_router)

@app.get('/booking')
def booking_page(): return FileResponse(ROOT/'passenger_app/booking.html')

@app.get('/register')
def register_page(): return FileResponse(ROOT/'passenger_app/register.html')


@app.get('/profile')
def profile_page(): return FileResponse(ROOT/'passenger_app/profile.html')
