from flask import Blueprint, render_template, abort, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Product, ProductVariant, Sale, User, SaleDetail, SalePayment, StockAdjustment, Expense, obtener_hora_bogota
from sqlalchemy.sql import func
from werkzeug.security import generate_password_hash
from decorators import admin_required
from decimal import Decimal

admin_bp = Blueprint('admin_bp', __name__)

@admin_bp.route('/vendedores', methods=['GET', 'POST'])
@login_required
@admin_required
def vendedores():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        email = request.form.get('email')
        telefono = request.form.get('telefono')
        password = request.form.get('password')
        rol = request.form.get('rol', 'vendedor')
        
        # Se previene registrar vendedores con un mismo email para preservar la unicidad de las credenciales de acceso
        if User.query.filter_by(email=email).first():
            flash('Acción Denegada: Ese correo ya le pertenece a otro usuario.', 'danger')
        else:
            try:
                # Se aplica un hash a la contraseña para evitar guardar texto plano, previniendo exposición en caso de brechas
                nuevo_usuario = User(
                    nombre=nombre.strip(),
                    email=email.strip(),
                    telefono=telefono.strip() if telefono else None,
                    password_hash=generate_password_hash(password),
                    rol=rol
                )
                db.session.add(nuevo_usuario)
                db.session.commit()
                flash(f"¡Usuario '{nombre}' registrado con rol '{rol}' exitosamente!", "success")
            except Exception as e:
                db.session.rollback()
                flash('Ocurrió un error en la base de datos al intentar registrar al usuario.', 'danger')
            
        return redirect(url_for('admin_bp.vendedores'))
        
    # Se pasa la lista para poblar la tabla HTML de gestión de personal
    # Mostramos todos los usuarios que no son admin para gestión centralizada
    lista_vendedores = User.query.filter(User.rol != 'admin').order_by(User.nombre).all()
    return render_template('admin/vendedores.html', vendedores=lista_vendedores)

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    # Se obtienen métricas clave para que el administrador tenga un resumen rápido de las operaciones del negocio
    total_productos = Product.query.count()
    # Alertar sobre insumos (materias primas) con stock igual o menor a 10
    productos_bajo_stock = Product.query.filter(
        Product.tipo_producto == 'insumo',
        Product.cantidad_stock <= 10
    ).count()
    
    # Se filtran las ventas del mes actual
    hoy = obtener_hora_bogota()
    inicio_mes = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    total_ventas = db.session.query(func.sum(Sale.monto_total)).filter(Sale.fecha_venta >= inicio_mes).scalar() or 0.0
    conteo_ventas = Sale.query.filter(Sale.fecha_venta >= inicio_mes).count()

    return render_template('admin/dashboard.html', 
                           total_productos=total_productos,
                           productos_bajo_stock=productos_bajo_stock,
                           total_ventas=total_ventas,
                           conteo_ventas=conteo_ventas)



@admin_bp.route('/balance-financiero', methods=['GET', 'POST'])
@login_required
@admin_required
def balance_financiero():
    if request.method == 'POST':
        fecha_inicio_str = request.form.get('fecha_inicio')
        fecha_fin_str = request.form.get('fecha_fin')
    else:
        fecha_inicio_str = request.args.get('fecha_inicio')
        fecha_fin_str = request.args.get('fecha_fin')

    hoy = obtener_hora_bogota()
    import calendar
    if not fecha_inicio_str or not fecha_fin_str:
        # Por defecto, el mes actual
        primer_dia = hoy.replace(day=1)
        ultimo_dia_mes = calendar.monthrange(hoy.year, hoy.month)[1]
        ultimo_dia = hoy.replace(day=ultimo_dia_mes)
        
        fecha_inicio_str = primer_dia.strftime('%Y-%m-%d')
        fecha_fin_str = ultimo_dia.strftime('%Y-%m-%d')

    from datetime import datetime, timedelta
    try:
        inicio_dt = datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
        fin_dt = datetime.strptime(fecha_fin_str, '%Y-%m-%d')
        # Avanzamos límite al inicio del siguiente día matemáticamente
        fin_dt_query = fin_dt + timedelta(days=1)
    except ValueError:
        flash("Formato de fecha inválido.", "danger")
        return redirect(url_for('admin_bp.dashboard'))

    # 1. Ventas Totales
    ventas_query = Sale.query.filter(Sale.fecha_venta >= inicio_dt, Sale.fecha_venta < fin_dt_query).all()
    ventas_efectivo = 0.0
    ventas_transferencia = 0.0
    
    for v in ventas_query:
        if v.pagos:
            for pago in v.pagos:
                monto = float(pago.monto)
                if pago.metodo_pago == 'efectivo':
                    ventas_efectivo += monto
                else:
                    ventas_transferencia += monto
        else:
            monto = float(v.monto_total)
            if v.metodo_pago == 'efectivo':
                ventas_efectivo += monto
            elif v.metodo_pago in ['transferencia', 'nequi', 'bancolombia', 'daviplata']:
                ventas_transferencia += monto
                
    total_ingresos = ventas_efectivo + ventas_transferencia

    # 2. Costo de Mercancía Vendida (COGS)
    detalles_query = SaleDetail.query.join(Sale).filter(
        Sale.fecha_venta >= inicio_dt,
        Sale.fecha_venta < fin_dt_query
    ).all()
    
    cantidades = {
        'perros_solos': 0,
        'perros_combo': 0,
        'gaseosas_pequenas': 0,
        'gaseosas_grandes': 0,
        'cortesias': 0
    }
    
    for d in detalles_query:
        # Detectar Cortesía
        if float(d.precio_venta_final) == 0.0:
            cantidades['cortesias'] += d.cantidad_vendida
        else:
            nombre_prod = d.producto.nombre.lower() if d.producto else (d.nombre_manual.lower() if d.nombre_manual else '')
            if 'sencillo' in nombre_prod or 'solo' in nombre_prod or ('perro' in nombre_prod and 'combo' not in nombre_prod) or ('hot dog' in nombre_prod and 'combo' not in nombre_prod):
                cantidades['perros_solos'] += d.cantidad_vendida
            elif 'combo' in nombre_prod:
                cantidades['perros_combo'] += d.cantidad_vendida
            elif 'peque' in nombre_prod or 'personal' in nombre_prod or 'mini' in nombre_prod:
                cantidades['gaseosas_pequenas'] += d.cantidad_vendida
            elif 'grande' in nombre_prod or 'litro' in nombre_prod or 'mega' in nombre_prod:
                cantidades['gaseosas_grandes'] += d.cantidad_vendida

    cantidades['total_perros_grueso'] = cantidades['perros_solos'] + cantidades['perros_combo'] + cantidades['cortesias']
    cantidades['total_gaseosas_pequenas_reales'] = cantidades['gaseosas_pequenas'] + cantidades['perros_combo']

    # 3. Costos Indirectos y Gastos Operativos
    gastos_query = Expense.query.filter(Expense.fecha_gasto >= inicio_dt, Expense.fecha_gasto < fin_dt_query).order_by(Expense.fecha_gasto.asc()).all()
    
    lista_costos_indirectos = [g for g in gastos_query if g.tipo_gasto == 'Costos Indirectos']
    lista_costos_producto = [g for g in gastos_query if g.tipo_gasto == 'Costos Producto']
    lista_gastos_operacionales = [g for g in gastos_query if g.tipo_gasto == 'Gastos Operacionales']
    
    costos_indirectos = sum(g.monto for g in lista_costos_indirectos)
    costos_producto = sum(g.monto for g in lista_costos_producto)
    gastos_operacionales = sum(g.monto for g in lista_gastos_operacionales)
    
    total_salidas = float(costos_indirectos) + float(costos_producto) + float(gastos_operacionales)
    balance_neto = float(total_ingresos) - total_salidas

    datos_financieros = {
        'ventas_efectivo': float(ventas_efectivo),
        'ventas_transferencia': float(ventas_transferencia),
        'total_ingresos': float(total_ingresos),
        'costos_indirectos': float(costos_indirectos),
        'costos_producto': float(costos_producto),
        'gastos_operacionales': float(gastos_operacionales),
        'total_salidas': total_salidas,
        'balance_neto': balance_neto,
        'cantidades': cantidades,
        'lista_costos_indirectos': lista_costos_indirectos,
        'lista_costos_producto': lista_costos_producto,
        'lista_gastos_operacionales': lista_gastos_operacionales
    }

    return render_template(
        'admin/balance_reporte.html',
        fecha_inicio=fecha_inicio_str,
        fecha_fin=fecha_fin_str,
        fecha_generacion=hoy.strftime('%Y-%m-%d %H:%M'),
        datos=datos_financieros
    )
