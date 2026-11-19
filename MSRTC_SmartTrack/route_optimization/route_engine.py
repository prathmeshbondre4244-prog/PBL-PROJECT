def recommend(routes):
    return sorted(routes, key=lambda x: (-x.get('score',0), x.get('duration',999)))[0]
