from datetime import date, datetime, timezone, timedelta
from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError

from config import Config
from models import db, User, Favorito, Historial
from nasa_service import consultar_nasa, consultar_nasa_rango, NASAServiceError

app = Flask(__name__)
app.config.from_object(Config)

if not app.config["JWT_SECRET_KEY"] or not app.config["NASA_API_KEY"]:
    raise RuntimeError("Configurar JWT_SECRET_KEY y NASA_API_KEY en .env")

db.init_app(app)
jwt = JWTManager(app)

@app.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    username, password = data.get("username"), data.get("password")
    
    if not isinstance(username, str) or not username.strip():
        return jsonify(error="El usuario es obligatorio"), 400
    if not isinstance(password, str) or len(password) < 8:
        return jsonify(error="La contraseña debe tener mínimo 8 caracteres"), 400
        
    db.session.add(User(username=username.strip(), password_hash=generate_password_hash(password)))
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="El usuario ya existe"), 409
        
    return jsonify(mensaje="Usuario registrado"), 201

@app.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    username, password = data.get("username"), data.get("password")
    
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify(error="Credenciales inválidas"), 401
        
    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify(error="Credenciales inválidas"), 401
        
    return jsonify(access_token=create_access_token(identity=str(user.id))), 200

def validar_fecha(fecha):
    try:
        valor = date.fromisoformat(fecha)
        if valor > date.today():
            return False
        return True
    except (ValueError, TypeError):
        return False

@app.get("/apod")
@jwt_required()
def apod():
    fecha = request.args.get("fecha")
    
    if fecha is not None:
        if not fecha.strip() or not validar_fecha(fecha):
            return jsonify(error="Fecha inválida o futura; usar YYYY-MM-DD"), 400
            
    try:
        datos = consultar_nasa(fecha)
    except NASAServiceError as e:
        return jsonify(error=str(e)), e.status_code
        
    db.session.add(Historial(fecha_imagen=datos["fecha"], user_id=int(get_jwt_identity())))
    db.session.commit()
    
    # Extraemos el rate limit para pasarlo como Header HTTP de Flask
    restantes = datos.pop("rate_limit_remaining", "No disponible")
    
    response = jsonify(datos)
    response.headers["X-RateLimit-Remaining"] = restantes
    return response, 200


# ENDPOINT PARA EL RETO A: Consulta por Rango
@app.get("/apod/rango")
@jwt_required()
def apod_rango():
    inicio_str = request.args.get("inicio")
    fin_str = request.args.get("fin")
    
    if not inicio_str or not fin_str:
        return jsonify(error="Se requieren los parámetros 'inicio' y 'fin' (YYYY-MM-DD)"), 400
        
    if not validar_fecha(inicio_str) or not validar_fecha(fin_str):
        return jsonify(error="Fechas inválidas o futuras; usar formato YYYY-MM-DD"), 400
        
    try:
        f_inicio = date.fromisoformat(inicio_str)
        f_fin = date.fromisoformat(fin_str)
    except (ValueError, TypeError):
        return jsonify(error="Formato de fecha inválido"), 400
        
    if f_inicio > f_fin:
        return jsonify(error="La fecha de inicio no puede ser posterior a la fecha fin"), 400
        
    diferencia = (f_fin - f_inicio).days
    if diferencia < 0 or diferencia > 15:
        return jsonify(error="El rango de fechas no puede superar los 15 días"), 400
        
    try:
        datos_lista, restantes = consultar_nasa_rango(inicio_str, fin_str)
    except NASAServiceError as e:
        return jsonify(error=str(e)), e.status_code
        
    user_id = int(get_jwt_identity())
    for item in datos_lista:
        db.session.add(Historial(fecha_imagen=item["fecha"], user_id=user_id))
    db.session.commit()
    
    response = jsonify(datos_lista)
    response.headers["X-RateLimit-Remaining"] = restantes
    return response, 200


@app.post("/favoritos")
@jwt_required()
def guardar_favorito():
    data = request.get_json(silent=True) or {}
    fecha = data.get("fecha")
    
    if not validar_fecha(fecha):
        return jsonify(error="Fecha inválida o futura"), 400
        
    try:
        datos = consultar_nasa(fecha)
    except NASAServiceError as e:
        return jsonify(error=str(e)), e.status_code
        
    fav = Favorito(
        titulo=datos["titulo"], 
        fecha=datos["fecha"],
        url_imagen=datos["url_imagen"], 
        user_id=int(get_jwt_identity())
    )
    db.session.add(fav)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="Publicación ya guardada"), 409
        
    return jsonify(mensaje="Favorito guardado", id=fav.id), 201

@app.get("/favoritos")
@jwt_required()
def favoritos():
    items = Favorito.query.filter_by(user_id=int(get_jwt_identity())).order_by(Favorito.id.desc()).all()
    return jsonify([{
        "id": x.id, 
        "titulo": x.titulo, 
        "fecha": x.fecha,
        "url_imagen": x.url_imagen
    } for x in items]), 200

@app.delete("/favoritos/<int:id>")
@jwt_required()
def eliminar_favorito(id):
    item = Favorito.query.filter_by(id=id, user_id=int(get_jwt_identity())).first()
    if item is None:
        return jsonify(error="Favorito no encontrado"), 404
        
    db.session.delete(item)
    db.session.commit()
    return jsonify(mensaje="Favorito eliminado"), 200

@app.get("/historial")
@jwt_required()
def historial():
    try:
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 10))
    except (ValueError, TypeError):
        return jsonify(error="Los parámetros 'page' y 'limit' deben ser enteros"), 400
        
    if page < 1 or limit < 1:
        return jsonify(error="Los parámetros 'page' y 'limit' deben ser mayores o iguales a 1"), 400
        
    if limit > 50:
        limit = 50
        
    user_id = int(get_jwt_identity())
    
    pagination = Historial.query.filter_by(user_id=user_id)\
        .order_by(Historial.fecha_consulta.desc())\
        .paginate(page=page, per_page=limit, error_out=False)
        
    resultados = [{
        "id": x.id, 
        "fecha_imagen": x.fecha_imagen,
        "fecha_consulta": x.fecha_consulta.isoformat()
    } for x in pagination.items]
    
    return jsonify({
        "pagina": pagination.page,
        "limite": pagination.per_page,
        "total": pagination.total,
        "resultados": resultados
    }), 200


@app.get("/estadisticas")
@jwt_required()
def estadisticas():
    user_id = int(get_jwt_identity())
    
    total_consultas = Historial.query.filter_by(user_id=user_id).count()
    total_favoritos = Favorito.query.filter_by(user_id=user_id).count()
    
    mas_consultada_row = db.session.query(
        Historial.fecha_imagen, db.func.count(Historial.fecha_imagen).label('total')
    ).filter_by(user_id=user_id)\
     .group_by(Historial.fecha_imagen)\
     .order_by(db.desc('total'))\
     .first()
     
    fecha_mas_consultada = mas_consultada_row.fecha_imagen if mas_consultada_row else None
    
    hace_siete_dias = datetime.now(timezone.utc) - timedelta(days=7)
    consultas_ultimos_7_dias = Historial.query.filter(
        Historial.user_id == user_id,
        Historial.fecha_consulta >= hace_siete_dias
    ).count()
    
    return jsonify({
        "total_consultas": total_consultas,
        "total_favoritos": total_favoritos,
        "fecha_mas_consultada": fecha_mas_consultada,
        "consultas_ultimos_7_dias": consultas_ultimos_7_dias
    }), 200


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)