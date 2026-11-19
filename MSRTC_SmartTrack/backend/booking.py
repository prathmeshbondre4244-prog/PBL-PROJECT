"""Educational reservation demo; not official MSRTC ticketing or fare rules."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime, timezone
from uuid import uuid4
import sqlite3

router=APIRouter(prefix='/api/booking', tags=['demo booking'])
DB=None

def configure(path):
    global DB
    DB=path
    with sqlite3.connect(DB) as c:
        c.execute('''CREATE TABLE IF NOT EXISTS demo_bookings(id TEXT PRIMARY KEY,bus_id TEXT,travel_date TEXT,details TEXT,total REAL,status TEXT,created_at TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS demo_seats(bus_id TEXT,travel_date TEXT,seat TEXT,booking_id TEXT,PRIMARY KEY(bus_id,travel_date,seat))''')

class Passenger(BaseModel):
    name:str=Field(min_length=1,max_length=100)
    age:int=Field(ge=0,le=120)
    gender:Literal['male','female','other']
    concession_verified:bool=False
    seat:str=Field(pattern=r'^[A-D][1-4]$')

class Booking(BaseModel):
    bus_id:str=Field(min_length=1,max_length=80)
    travel_date:str
    base_fare:float=Field(gt=0,le=100000)
    passengers:list[Passenger]=Field(min_length=1,max_length=6)

def amount(p,base):
    # DEMO ONLY: editable sample discount; NOT a representation of MSRTC policy.
    rate=0.5 if p.concession_verified and (p.gender=='female' or p.age>=65) else 1.0
    return round(base*rate,2)

@router.get('/seats')
def seats(bus_id:str, travel_date:str):
    with sqlite3.connect(DB) as c:
        rows=c.execute('SELECT seat FROM demo_seats WHERE bus_id=? AND travel_date=?',(bus_id,travel_date)).fetchall()
    return {'occupied':[r[0] for r in rows]}

@router.post('/quote')
def quote(b:Booking):
    if len({p.seat for p in b.passengers})!=len(b.passengers):
        raise HTTPException(400,'Each passenger must have a unique seat')
    fares=[amount(p,b.base_fare) for p in b.passengers]
    return {'fares':fares,'total':round(sum(fares),2),'notice':'Illustrative fare rules only. Concessions are not verified with MSRTC.'}

@router.post('/reserve')
def reserve(b:Booking):
    try: datetime.strptime(b.travel_date,'%Y-%m-%d')
    except ValueError: raise HTTPException(400,'Invalid travel date')
    if b.travel_date<datetime.now().date().isoformat(): raise HTTPException(400,'Travel date must not be in the past')
    if len({p.seat for p in b.passengers})!=len(b.passengers): raise HTTPException(400,'Duplicate seat selected')
    import json
    booking_id='DEMO-'+uuid4().hex[:10].upper()
    details=json.dumps(b.model_dump())
    total=quote(b)['total']
    try:
        with sqlite3.connect(DB,timeout=10) as c:
            c.execute('BEGIN IMMEDIATE')
            for p in b.passengers:
                c.execute('INSERT INTO demo_seats VALUES (?,?,?,?)',(b.bus_id,b.travel_date,p.seat,booking_id))
            c.execute('INSERT INTO demo_bookings VALUES (?,?,?,?,?,?,?)',(booking_id,b.bus_id,b.travel_date,details,total,'AWAITING_DEMO_PAYMENT',datetime.now(timezone.utc).isoformat()))
    except sqlite3.IntegrityError: raise HTTPException(409,'One or more seats are no longer available. Refresh seats.')
    return {'booking_id':booking_id,'total':total,'status':'AWAITING_DEMO_PAYMENT'}

@router.post('/demo-pay/{booking_id}')
def demo_pay(booking_id:str):
    with sqlite3.connect(DB) as c:
        row=c.execute('SELECT status FROM demo_bookings WHERE id=?',(booking_id,)).fetchone()
        if not row: raise HTTPException(404,'Booking not found')
        if row[0]!='AWAITING_DEMO_PAYMENT': raise HTTPException(409,'Payment already processed')
        c.execute('UPDATE demo_bookings SET status=? WHERE id=?',('DEMO_CONFIRMED',booking_id))
    return {'booking_id':booking_id,'status':'DEMO_CONFIRMED','notice':'Simulated payment only. No real money collected.'}

@router.get('/ticket/{booking_id}')
def ticket(booking_id:str):
    import json
    with sqlite3.connect(DB) as c:
        row=c.execute('SELECT bus_id,travel_date,details,total,status FROM demo_bookings WHERE id=?',(booking_id,)).fetchone()
    if not row: raise HTTPException(404,'Booking not found')
    details=json.loads(row[2]); details.pop('base_fare',None)
    return {'booking_id':booking_id,'bus_id':row[0],'travel_date':row[1], 'passengers':details['passengers'],'total':row[3],'status':row[4], 'notice':'DEMO TICKET — NOT VALID FOR TRAVEL'}

# Individual endpoints: passenger identity is taken from the saved authenticated profile, not editable form fields.
from fastapi import Header
from datetime import date

def individual_payload(b, authorization):
    from backend.main import current_profile
    profile=current_profile(authorization)
    if len(b.passengers)!=1: raise HTTPException(400,'Individual booking requires exactly one passenger')
    try: travel=date.fromisoformat(b.travel_date)
    except ValueError: raise HTTPException(400,'Invalid travel date')
    dob=date.fromisoformat(profile['date_of_birth'])
    age=travel.year-dob.year-((travel.month,travel.day)<(dob.month,dob.day))
    if age<0: raise HTTPException(400,'Travel date precedes date of birth')
    p=b.passengers[0]
    # No concession is automatically verified just because the user claimed a card.
    return b.model_copy(update={'passengers':[Passenger(name=profile['name'],age=age,gender=profile['gender'] if profile['gender'] in ('male','female','other') else 'other',concession_verified=False,seat=p.seat)]})

@router.post('/individual/quote')
def individual_quote(b:Booking, authorization:str=Header(default='')):
    return quote(individual_payload(b,authorization))

@router.post('/individual/reserve')
def individual_reserve(b:Booking, authorization:str=Header(default='')):
    return reserve(individual_payload(b,authorization))
