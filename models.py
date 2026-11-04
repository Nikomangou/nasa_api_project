from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

class Favorito(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    fecha = db.Column(db.String(20), nullable=False)
    url_imagen = db.Column(db.String(1000))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    
    __table_args__ = (db.UniqueConstraint("user_id", "fecha", name="uq_usuario_fecha"),)

class Historial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha_consulta = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    fecha_imagen = db.Column(db.String(20), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)