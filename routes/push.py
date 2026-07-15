import os
import json
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from models import db, PushSubscription
import pywebpush

push_bp = Blueprint('push_bp', __name__)

@push_bp.route('/subscribe', methods=['POST'])
@login_required
def subscribe():
    subscription_info = request.get_json()
    if not subscription_info:
        return jsonify({"error": "No subscription data provided"}), 400

    endpoint = subscription_info.get('endpoint')
    keys = subscription_info.get('keys', {})
    p256dh = keys.get('p256dh')
    auth = keys.get('auth')

    if not endpoint or not p256dh or not auth:
        return jsonify({"error": "Invalid subscription data"}), 400

    # Evitar duplicados
    existing_sub = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if existing_sub:
        if existing_sub.usuario_id != current_user.id:
            existing_sub.usuario_id = current_user.id
            db.session.commit()
        return jsonify({"message": "Subscription updated"}), 200

    new_sub = PushSubscription(
        usuario_id=current_user.id,
        endpoint=endpoint,
        p256dh=p256dh,
        auth=auth
    )
    
    try:
        db.session.add(new_sub)
        db.session.commit()
        return jsonify({"message": "Subscription created"}), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Error guardando suscripción push", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

def send_push_notification(user_id, title, body, url="/"):
    """
    Función utilitaria para enviar notificaciones a un usuario específico.
    Se puede importar y usar en cualquier parte del sistema.
    """
    subs = PushSubscription.query.filter_by(usuario_id=user_id).all()
    if not subs:
        return

    vapid_private_key = os.environ.get('VAPID_PRIVATE_KEY', 'private_key.pem')
    vapid_claims = {
        "sub": "mailto:" + os.environ.get('VAPID_CLAIM_EMAIL', 'admin@elgoldy.com')
    }

    if not os.path.exists(vapid_private_key) and vapid_private_key == 'private_key.pem':
        current_app.logger.warning("No se encontró private_key.pem ni VAPID_PRIVATE_KEY. No se enviará el push.")
        return

    for sub in subs:
        subscription_info = {
            "endpoint": sub.endpoint,
            "keys": {
                "p256dh": sub.p256dh,
                "auth": sub.auth
            }
        }
        
        try:
            pywebpush.webpush(
                subscription_info=subscription_info,
                data=json.dumps({"title": title, "body": body, "url": url}),
                vapid_private_key=vapid_private_key,
                vapid_claims=vapid_claims
            )
        except pywebpush.WebPushException as ex:
            current_app.logger.error(f"WebPushException: {repr(ex)}")
            # Si el endpoint expiró (ej. error 410), podríamos borrar la suscripción de la BD
            if ex.response and ex.response.status_code == 410:
                db.session.delete(sub)
                db.session.commit()
