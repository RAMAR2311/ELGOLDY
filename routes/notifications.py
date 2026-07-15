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
    page = request.args.get('page', 1, type=int)
    # Obtener todas las notificaciones paginadas
    pagination = Notification.query.order_by(desc(Notification.fecha_creacion)).paginate(page=page, per_page=30, error_out=False)
    
    # Marcar como leídas
    for notif in pagination.items:
        if not notif.leida:
            notif.leida = True
    db.session.commit()

    return render_template('notifications/index.html', pagination=pagination)
