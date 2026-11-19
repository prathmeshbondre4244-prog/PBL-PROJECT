# MSRTC SmartTrack

**Problem Statement:** Enhancing MSRTC Commuter Experience with Smart Real-Time Bus Tracking and Route Optimization.

This project is a functional prototype for smart MSRTC commuter services.

## Main modules
- Passenger application
- Driver/GPS simulator
- Admin dashboard
- Real-time bus tracking
- ETA calculation
- Delay detection
- Smart route optimization
- Route and bus data
- FastAPI backend

## Run
```bash
pip install -r requirements.txt
python run.py
```
Then open:
- Passenger: http://127.0.0.1:8000/
- Dashboard: http://127.0.0.1:8000/dashboard/
- Driver: http://127.0.0.1:8000/driver/

## Live tracking demo
1. Start the backend.
2. Open the Driver page.
3. Click **Start GPS Simulation**.
4. Open the Passenger page in another browser tab.
5. Select **Live Tracking**.
6. The bus marker and GPS values update automatically.

The simulator represents the GPS/AVL device that would be installed on a real bus. For deployment, it can be replaced by an authorized MSRTC GPS feed or driver-device GPS source.


## Login Page
Open `http://127.0.0.1:8000/login` for the role-based login screen.
Demo accounts:
- Passenger: passenger@msrtc.com / passenger123
- Driver: driver@msrtc.com / driver123
- Admin: admin@msrtc.com / admin123

The login is a demo authentication flow. For production, passwords should be hashed and real user authentication/session management should be used.


## Family booking demonstration
Run `python run.py` and open `http://127.0.0.1:8000/booking`. Supports 1–6 passengers, age/gender details, sample concession checkbox, 16 demo seats per bus/date, SQLite reservations, demo payment confirmation and printable ticket. This is NOT official MSRTC booking, fare eligibility, payment, or seat inventory. No real money is collected. Concession verification checkbox is a demo flag only.

## Home page booking shortcut
The Home screen now has a prominent **Book Tickets · Enter Age & Gender** button and a **Family booking** feature tile. The bottom **Book** navigation item also opens `/booking`. From the booking page, use **Back to Home** to return. Booking and payment remain academic simulations.
