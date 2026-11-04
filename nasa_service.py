import requests
from flask import current_app

class NASAServiceError(Exception):
    def __init__(self, mensaje, status_code=502):
        super().__init__(mensaje)
        self.status_code = status_code

def consultar_nasa(fecha=None):
    params = {"api_key": current_app.config["NASA_API_KEY"]}
    if fecha:
        params["date"] = fecha
        
    try:
        r = requests.get("https://api.nasa.gov/planetary/apod", params=params, timeout=10)
        
        if r.status_code == 400:
            raise NASAServiceError("Parámetros rechazados por NASA", 400)
        if r.status_code in (401, 403):
            raise NASAServiceError("Error de autorización con NASA", 502)
        if r.status_code == 429:
            raise NASAServiceError("Límite de consultas de NASA", 503)
            
        r.raise_for_status()
        data = r.json()
        
        # Capturamos el header de la NASA
        rate_limit_remaining = r.headers.get("X-RateLimit-Remaining", "No disponible")
        
        return {
            "titulo": data["title"],
            "fecha": data["date"],
            "explicacion": data["explanation"],
            "url_imagen": data.get("url"),
            "tipo": data.get("media_type"),
            "rate_limit_remaining": rate_limit_remaining
        }
    except requests.exceptions.Timeout:
        raise NASAServiceError("NASA no respondió a tiempo", 504)
    except requests.exceptions.RequestException:
        raise NASAServiceError("Error de comunicación con NASA", 502)
    except (ValueError, KeyError, TypeError):
        raise NASAServiceError("Respuesta inválida de NASA", 502)


# FUNCIÓN EXTRA PARA EL RETO A (Rango de fechas)
def consultar_nasa_rango(inicio, fin):
    params = {
        "api_key": current_app.config["NASA_API_KEY"],
        "start_date": inicio,
        "end_date": fin
    }
    
    try:
        r = requests.get("https://api.nasa.gov/planetary/apod", params=params, timeout=15)
        
        if r.status_code == 400:
            raise NASAServiceError("Parámetros de rango rechazados por NASA", 400)
        if r.status_code in (401, 403):
            raise NASAServiceError("Error de autorización con NASA", 502)
        if r.status_code == 429:
            raise NASAServiceError("Límite de consultas de NASA", 503)
            
        r.raise_for_status()
        data = r.json()
        
        rate_limit_remaining = r.headers.get("X-RateLimit-Remaining", "No disponible")
        
        resultados = []
        for item in data:
            resultados.append({
                "titulo": item.get("title"),
                "fecha": item.get("date"),
                "explicacion": item.get("explanation"),
                "url_imagen": item.get("url"),
                "tipo": item.get("media_type")
            })
        return resultados, rate_limit_remaining
        
    except requests.exceptions.Timeout:
        raise NASAServiceError("NASA no respondió a tiempo", 504)
    except requests.exceptions.RequestException:
        raise NASAServiceError("Error de comunicación con NASA", 502)
    except (ValueError, KeyError, TypeError):
        raise NASAServiceError("Respuesta inválida de NASA", 502)