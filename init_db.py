from app import app
from models import db

if __name__ == '__main__':
    with app.app_context():
        print("Creando tablas faltantes en la base de datos...")
        db.create_all()
        print("¡Tablas creadas exitosamente!")
