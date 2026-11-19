import time, json, urllib.request
ROUTE=[(18.5284,73.8739),(18.5196,73.8719),(18.5100,73.8675),(18.5018,73.8636),(18.4900,73.8645),(18.4750,73.8660),(18.4620,73.8670),(18.4529,73.8662),(18.6200,73.7000),(18.7000,73.5600),(18.7481,73.4072)]
STOPS=['Pune Station','Pune City','Swargate','Katraj','Khopoli','Lonavala','Mumbai Expressway','Mumbai']
def run(bus_id='MH12AB1234'):
    for i,(lat,lon) in enumerate(ROUTE):
        payload={'bus_id':bus_id,'latitude':lat,'longitude':lon,'speed':42 if i<7 else 55,'eta':max(3,18-i),'status':'ON_TIME','current_stop':STOPS[min(i,len(STOPS)-1)]}
        req=urllib.request.Request('http://127.0.0.1:8000/api/location',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
        try: urllib.request.urlopen(req,timeout=3).read(); print('GPS sent:',payload)
        except Exception as e: print('Backend unavailable:',e)
        time.sleep(2)
if __name__=='__main__':
    while True: run()
