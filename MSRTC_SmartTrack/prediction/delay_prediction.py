def predict_delay(speed, traffic='LOW'):
    if traffic.upper() == 'HIGH' or speed < 20: return {'risk':'HIGH','minutes':15}
    if traffic.upper() == 'MEDIUM' or speed < 35: return {'risk':'MEDIUM','minutes':7}
    return {'risk':'LOW','minutes':0}
