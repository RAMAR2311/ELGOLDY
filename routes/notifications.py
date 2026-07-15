from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import db, Notification
from decorators import admin_required
from sqlalchemy import desc

notifications_bp = Blueprint('notifications_bp', __name__)

@notifications_bp.route('/', methods=['GET'])
@login_required
@admin_required
def index():
    # Obtener todas las notificaciones ordenadas de más reciente a más antigua
    notificaciones = Notification.query.order_by(desc(Notification.fecha_creacion)).all()
    
    # Marcar como leídas
    for notif in notificaciones:
        if not notif.leida:
            notif.leida = True
    db.session.commit()

    return render_template('notifications/index.html', notificaciones=notificaciones)
