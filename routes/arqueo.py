from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from models import db, Sale, SalePayment, ArqueoCaja, Expense, Product, User, Notification
from decorators import admin_required
from routes.push import send_push_notification
from datetime import datetime, date
from decimal import Decimal
import re
import pytz
from sqlalchemy.exc import IntegrityError
from services.arqueo_service import ArqueoService

arqueo_bp = Blueprint('arqueo_bp', __name__)

def obtener_hora_bogota():
    return datetime.now(pytz.timezone('America/Bogota')).replace(tzinfo=None)

@arqueo_bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo():
    # Obtener fecha de la URL o usar hoy
    fecha_str = request.args.get('fecha', obtener_hora_bogota().strftime('%Y-%m-%d'))
    try:
        fecha_seleccionada = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except ValueError:
        fecha_seleccionada = obtener_hora_bogota().date()
        fecha_str = fecha_seleccionada.strftime('%Y-%m-%d')

    # Calcular ventas del día usando el sistema híbrido (SalePayment + legacy)
    ventas_del_dia = Sale.query.filter(db.func.date(Sale.fecha_venta) == fecha_seleccionada).all()
    total_efectivo, total_transferencia = ArqueoService.calcular_totales_dia(ventas_del_dia)

    # Calcular cantidades de productos vendidos en el día
    resumen_ventas_productos = ArqueoService.obtener_resumen_productos(ventas_del_dia)

    # Obtener stock de insumos clave (Pan y Salchicha)
    producto_pan = Product.query.filter(Product.nombre.ilike('%pan%')).first()
    producto_salchicha = Product.query.filter(Product.nombre.ilike('%salchicha%')).first()
    stock_pan = producto_pan.total_stock if producto_pan else 0
    stock_salchicha = producto_salchicha.total_stock if producto_salchicha else 0

    # Calcular gastos automáticos del día
    gastos_automaticos = ArqueoService.calcular_gastos_automaticos(fecha_seleccionada)

    # Calcular gastos por productos externos del día
    gastos_externos = ArqueoService.calcular_gastos_externos(fecha_seleccionada)

    # Verificar si ya existe un arqueo GLOBAL para esa fecha (unificado para todos los usuarios)
    arqueo_existente = ArqueoCaja.query.filter_by(fecha_arqueo=fecha_seleccionada).first()

    # Calcular base sugerida desde el arqueo anterior
    base_sugerida = ArqueoService.obtener_base_sugerida(fecha_seleccionada)

    if request.method == 'POST':
        # Validación inicial
        if ArqueoCaja.query.filter_by(fecha_arqueo=fecha_seleccionada).first():
            flash('Ya existe un arqueo cerrado para esta fecha. No se puede duplicar.', 'warning')
            return redirect(url_for('arqueo_bp.reporte', fecha_inicio=fecha_str, fecha_fin=fecha_str))

        base_inicial = Decimal(request.form.get('base_inicial', '0.0'))
        retiro_grueso = Decimal(request.form.get('retiro_grueso', '0.0'))
        
        # Recalcular gastos automáticos por seguridad en el backend
        gastos_del_dia = ArqueoService.calcular_gastos_automaticos(fecha_seleccionada)
        
        observaciones_gastos = request.form.get('observaciones_gastos', '').strip()

        nuevo_arqueo = ArqueoCaja(
            vendedor_id=current_user.id,
            fecha_arqueo=fecha_seleccionada,
            base_inicial=base_inicial,
            gastos_del_dia=gastos_del_dia,
            retiro_grueso=retiro_grueso,
            observaciones_gastos=observaciones_gastos,
            total_efectivo_sistema=total_efectivo,
            total_transferencia_sistema=total_transferencia
        )

        try:
            db.session.add(nuevo_arqueo)
            db.session.commit()

            # Notificación de cierre de caja a administradores
            admins = User.query.filter_by(rol='admin').all()
            mensaje = f'Se generó el cierre de caja del día "{fecha_str}" revisalo desde tu app.'
            titulo = 'Cierre de Caja'
            
            nueva_notificacion = Notification(
                tipo='arqueo',
                titulo=titulo,
                mensaje=mensaje
            )
            db.session.add(nueva_notificacion)
            db.session.commit()
            
            for admin_user in admins:
                send_push_notification(
                    user_id=admin_user.id,
                    title=titulo,
                    body=mensaje,
                    url='/arqueo/reporte'
                )

            flash('Arqueo de caja guardado exitosamente.', 'success')
            return redirect(url_for('arqueo_bp.reporte', fecha_inicio=fecha_str, fecha_fin=fecha_str))
        except IntegrityError as e:
            db.session.rollback()
            current_app.logger.warning(f"Intento duplicado de crear arqueo detectado y prevenido: {e}")
            flash('Ya existe un arqueo para esta fecha (Condición de Carrera Prevenida).', 'warning')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error("Error crítico al guardar arqueo de caja.", exc_info=True)
            flash('Ocurrió un error interno al guardar el arqueo de caja.', 'danger')

    return render_template(
        'arqueo/form.html',
        fecha=fecha_str,
        total_efectivo=total_efectivo,
        total_transferencia=total_transferencia,
        arqueo_existente=arqueo_existente,
        gastos_automaticos=gastos_automaticos,
        gastos_externos=gastos_externos,
        base_sugerida=base_sugerida,
        resumen_ventas_productos=resumen_ventas_productos,
        stock_pan=stock_pan,
        stock_salchicha=stock_salchicha
    )

@arqueo_bp.route('/reporte', methods=['GET'])
@login_required
def reporte():
    fecha_inicio_str = request.args.get('fecha_inicio', obtener_hora_bogota().strftime('%Y-%m-%d'))
    fecha_fin_str = request.args.get('fecha_fin', obtener_hora_bogota().strftime('%Y-%m-%d'))

    try:
        fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
        fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
    except ValueError:
        fecha_inicio = obtener_hora_bogota().date()
        fecha_fin = obtener_hora_bogota().date()


    # Arqueo unificado: todos los usuarios ven los mismos arqueos (ya no se filtra por vendedor)
    query = ArqueoCaja.query.filter(ArqueoCaja.fecha_arqueo >= fecha_inicio, ArqueoCaja.fecha_arqueo <= fecha_fin)

    arqueos = query.order_by(ArqueoCaja.fecha_arqueo.desc()).all()

    # Cálculos globales para el reporte
    resumen = {
        'total_base': sum(a.base_inicial for a in arqueos),
        'total_efectivo': sum(a.total_efectivo_sistema for a in arqueos),
        'total_transferencia': sum(a.total_transferencia_sistema for a in arqueos),
        'total_gastos': sum(a.gastos_del_dia for a in arqueos)
    }
    
    resumen['total_recaudado_bruto'] = resumen['total_efectivo'] + resumen['total_transferencia']
    # Restar TOTAL DE GASTOS de la venta neta (Los gastos externos ya están incluidos en total_gastos si se registran como Gasto Diario)
    resumen['total_recaudado_neto'] = resumen['total_recaudado_bruto'] - resumen['total_gastos']
    
    # Calcular los gastos que fueron pagados en EFECTIVO
    gastos_efectivo_query = Expense.query.filter(
        db.func.date(Expense.fecha_gasto) >= fecha_inicio,
        db.func.date(Expense.fecha_gasto) <= fecha_fin,
        Expense.metodo_pago == 'efectivo'
    ).all()
    resumen['total_gastos_efectivo'] = sum(g.monto for g in gastos_efectivo_query)

    # El efectivo esperado en caja descuenta gastos en EFECTIVO
    resumen['efectivo_esperado'] = (resumen['total_base'] + resumen['total_efectivo']) - resumen['total_gastos_efectivo']

    # Obtener todas las ventas del periodo para el detalle en la "tirilla" (unificado)
    ventas_query = Sale.query.filter(
        db.func.date(Sale.fecha_venta) >= fecha_inicio,
        db.func.date(Sale.fecha_venta) <= fecha_fin
    )
    
    ventas_periodo = ventas_query.order_by(Sale.fecha_venta.asc()).all()

    fecha_generacion = obtener_hora_bogota().strftime('%Y-%m-%d %H:%M')


    
    # Obtener todos los gastos del periodo para el reporte detallado
    gastos_periodo = Expense.query.filter(
        db.func.date(Expense.fecha_gasto) >= fecha_inicio,
        db.func.date(Expense.fecha_gasto) <= fecha_fin
    ).order_by(Expense.fecha_gasto.asc()).all()

    return render_template(
        'arqueo/reporte.html',
        arqueos=arqueos,
        resumen=resumen,
        fecha_inicio=fecha_inicio_str,
        fecha_fin=fecha_fin_str,
        fecha_generacion=fecha_generacion,
        ventas_periodo=ventas_periodo,
        gastos_periodo=gastos_periodo
    )

@arqueo_bp.route('/reabrir/<int:arqueo_id>', methods=['POST'])
@login_required
@admin_required
def reabrir(arqueo_id):
    arqueo = ArqueoCaja.query.get_or_404(arqueo_id)
    try:
        db.session.delete(arqueo)
        db.session.commit()
        flash('Arqueo reabierto exitosamente. El cierre ha sido anulado y se puede volver a calcular.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error crítico al intentar reabrir el arqueo {arqueo_id}.", exc_info=True)
        flash('Ocurrió un error interno al intentar reabrir el arqueo.', 'danger')
    
    # Redirigir al reporte manteniendo los parámetros de fecha si es posible, 
    # o a la ruta base de reporte
    return redirect(url_for('arqueo_bp.reporte'))

