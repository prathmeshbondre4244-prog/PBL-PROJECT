def calculate_eta(distance_km, speed_kmh):
    if speed_kmh <= 0: return None
    return round((distance_km / speed_kmh) * 60)
