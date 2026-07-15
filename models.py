from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import pytz

db = SQLAlchemy()

def obtener_hora_bogota():
    """Inyecta el uso de red horario en Colombia a nivel de sistema operativo."""
    return datetime.now(pytz.timezone('America/Bogota')).replace(tzinfo=None)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    telefono = db.Column(db.String(20)) # Nuevo Campo de Contacto (Nullable por Defecto)
    password_hash = db.Column(db.String(256), nullable=False)
    rol = db.Column(db.String(50), nullable=False, default='cajero')
    
    ventas = db.relationship('Sale', backref='vendedor', lazy=True)
    ajustes_stock = db.relationship('StockAdjustment', backref='admin', lazy=True)
    arqueos = db.relationship('ArqueoCaja', backref='cajero', lazy=True)

    def __init__(self, nombre=None, email=None, telefono=None, password_hash=None, rol=None, **kwargs):
        if nombre is not None: kwargs['nombre'] = nombre
        if email is not None: kwargs['email'] = email
        if telefono is not None: kwargs['telefono'] = telefono
        if password_hash is not None: kwargs['password_hash'] = password_hash
        if rol is not None: kwargs['rol'] = rol
        super(User, self).__init__(**kwargs)

class Categoria(db.Model):
    __tablename__ = 'categorias'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False, unique=True)
    
    productos = db.relationship('Product', backref='categoria', lazy=True)

    def __init__(self, **kwargs):
        super(Categoria, self).__init__(**kwargs)

class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    sku = db.Column(db.String(50), unique=True, nullable=False, index=True)
    tipo_producto = db.Column(db.String(50), nullable=False, server_default='producto_final') # 'insumo', 'producto_final', 'adicional'
    categoria_id = db.Column(db.Integer, db.ForeignKey('categorias.id'), nullable=True)
    cantidad_stock = db.Column(db.Integer, nullable=False, default=0)
    precio_costo = db.Column(db.Numeric(10, 2), nullable=False, default=0.00) # El Costo de Bodega
    precio_minimo = db.Column(db.Numeric(10, 2), nullable=False)
    precio_sugerido = db.Column(db.Numeric(10, 2), nullable=False)
    imagen = db.Column(db.String(255), nullable=True) # Nombre de la foto subida
    observacion = db.Column(db.Text, nullable=True) # Nota descriptiva
    fecha_creacion = db.Column(db.DateTime, default=obtener_hora_bogota)
    
    detalles_venta = db.relationship('SaleDetail', backref='producto', lazy=True)
    ajustes_stock = db.relationship('StockAdjustment', backref='producto_rel', lazy=True)
    variantes = db.relationship('ProductVariant', backref='producto', lazy=True, cascade="all, delete-orphan")
    recetas = db.relationship('Receta', foreign_keys='Receta.producto_final_id', backref='producto_final', lazy=True, cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        super(Product, self).__init__(**kwargs)

    @property
    def total_stock(self):
        if self.variantes:
            return sum(v.cantidad_stock for v in self.variantes)
        return self.cantidad_stock

    @property
    def rango_precios(self):
        if not self.variantes:
            return None
        precios = [v.precio_sugerido for v in self.variantes if v.precio_sugerido is not None]
        if not precios:
            return None
        min_p = min(precios)
        max_p = max(precios)
        if min_p == max_p:
            return min_p
        return (min_p, max_p)

    @property
    def rango_costos(self):
        if not self.variantes:
            return None
        precios = [v.precio_costo for v in self.variantes if v.precio_costo is not None]
        if not precios:
            return None
        min_p = min(precios)
        max_p = max(precios)
        if min_p == max_p:
            return min_p
        return (min_p, max_p)

    @property
    def rango_minimos(self):
        if not self.variantes:
            return None
        precios = [v.precio_minimo for v in self.variantes if v.precio_minimo is not None]
        if not precios:
            return None
        min_p = min(precios)
        max_p = max(precios)
        if min_p == max_p:
            return min_p
        return (min_p, max_p)

class ProductVariant(db.Model):
    __tablename__ = 'product_variants'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    nombre_variante = db.Column(db.String(100), nullable=False)
    cantidad_stock = db.Column(db.Integer, nullable=False, default=0)
    
    # Nuevos precios específicos para variantes
    precio_costo = db.Column(db.Numeric(10, 2), nullable=True) 
    precio_minimo = db.Column(db.Numeric(10, 2), nullable=True)
    precio_sugerido = db.Column(db.Numeric(10, 2), nullable=True)

    def __init__(self, **kwargs):
        super(ProductVariant, self).__init__(**kwargs)

class Receta(db.Model):
    """Modelo para vincular un producto final (ej. Hot Dog) con sus insumos (Pan, Salchicha)."""
    __tablename__ = 'recetas'
    
    id = db.Column(db.Integer, primary_key=True)
    producto_final_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    insumo_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    cantidad_requerida = db.Column(db.Numeric(10, 2), nullable=False, default=1.0) # Cuántas unidades del insumo requiere
    
    insumo = db.relationship('Product', foreign_keys=[insumo_id])

    def __init__(self, **kwargs):
        super(Receta, self).__init__(**kwargs)

class Sale(db.Model):
    __tablename__ = 'sales'
    
    id = db.Column(db.Integer, primary_key=True)
    vendedor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    fecha_venta = db.Column(db.DateTime, default=obtener_hora_bogota)
    monto_total = db.Column(db.Numeric(10, 2), nullable=False, default=0.0)
    metodo_pago = db.Column(db.String(50), nullable=False, default='efectivo')
    numero_turno = db.Column(db.Integer, nullable=True) # Turno del día para llamar al cliente
    
    detalles = db.relationship('SaleDetail', backref='venta', lazy=True, cascade="all, delete-orphan")
    pagos = db.relationship('SalePayment', backref='venta', lazy=True, cascade="all, delete-orphan")
    cliente = db.relationship('SaleClient', backref='venta', lazy=True, cascade="all, delete-orphan", uselist=False)

    def __init__(self, **kwargs):
        super(Sale, self).__init__(**kwargs)

    @property
    def metodo_pago_display(self):
        """Retorna un resumen legible del método de pago.
        Si es pago único, retorna el nombre del método.
        Si es mixto, retorna 'Pago Mixto' con desglose."""
        if not self.pagos:
            # Retrocompatibilidad con ventas antiguas que solo tienen metodo_pago
            return self.metodo_pago.capitalize() if self.metodo_pago else 'Efectivo'
        if len(self.pagos) == 1:
            return self.pagos[0].metodo_pago.capitalize()
        return 'Pago Mixto'

class SalePayment(db.Model):
    """Modelo para soportar pagos mixtos/parciales por venta.
    Permite registrar múltiples métodos de pago en una sola venta.
    Ej: $50.000 en efectivo + $30.000 por Nequi = $80.000 total."""
    __tablename__ = 'sale_payments'

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    metodo_pago = db.Column(db.String(50), nullable=False)  # efectivo, nequi, bancolombia, daviplata
    monto = db.Column(db.Numeric(10, 2), nullable=False)

    def __init__(self, **kwargs):
        super(SalePayment, self).__init__(**kwargs)

class SaleClient(db.Model):
    """Modelo para almacenar los datos del cliente, especialmente requerido en ventas de celulares."""
    __tablename__ = 'sale_clients'
    
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False, unique=True)
    nombre = db.Column(db.String(150), nullable=False)
    documento = db.Column(db.String(50), nullable=False, index=True)
    telefono = db.Column(db.String(50), nullable=False)
    
    # Relación configurada desde Sale

    def __init__(self, **kwargs):
        super(SaleClient, self).__init__(**kwargs)

class SaleDetail(db.Model):
    __tablename__ = 'sale_details'
    
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_variants.id'), nullable=True)
    cantidad_vendida = db.Column(db.Integer, nullable=False)
    precio_venta_final = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Notas del cliente para modificaciones (ej. "Sin cebolla")
    notas = db.Column(db.String(255), nullable=True)

    variante = db.relationship('ProductVariant', backref='ventas_rel', lazy=True)

    def __init__(self, **kwargs):
        super(SaleDetail, self).__init__(**kwargs)

class StockAdjustment(db.Model):
    __tablename__ = 'stock_adjustments'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    tipo_movimiento = db.Column(db.String(100), nullable=True) # Ej: Creación Inicial, Ajuste Manual
    stock_anterior = db.Column(db.Integer, nullable=False)
    stock_nuevo = db.Column(db.Integer, nullable=False)
    fecha_ajuste = db.Column(db.DateTime, default=obtener_hora_bogota)

    def __init__(self, **kwargs):
        super(StockAdjustment, self).__init__(**kwargs)

class ArqueoCaja(db.Model):
    __tablename__ = 'arqueo_caja'
    
    id = db.Column(db.Integer, primary_key=True)
    vendedor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    fecha_arqueo = db.Column(db.Date, nullable=False, unique=True)
    base_inicial = db.Column(db.Numeric(10, 2), nullable=False, default=0.0)
    gastos_del_dia = db.Column(db.Numeric(10, 2), nullable=False, default=0.0)
    retiro_grueso = db.Column(db.Numeric(10, 2), nullable=False, default=0.0)
    observaciones_gastos = db.Column(db.String(255), nullable=True)
    total_efectivo_sistema = db.Column(db.Numeric(10, 2), nullable=False, default=0.0)
    total_transferencia_sistema = db.Column(db.Numeric(10, 2), nullable=False, default=0.0)
    fecha_creacion = db.Column(db.DateTime, default=obtener_hora_bogota)

    def __init__(self, **kwargs):
        super(ArqueoCaja, self).__init__(**kwargs)

class Expense(db.Model):
    __tablename__ = 'expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    tipo_gasto = db.Column(db.String(50), nullable=False) # 'Gasto Diario' o 'Costo Indirecto'
    categoria = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.String(255), nullable=True)
    monto = db.Column(db.Numeric(10, 2), nullable=False)
    metodo_pago = db.Column(db.String(50), nullable=False, default='efectivo')
    fecha_gasto = db.Column(db.DateTime, default=obtener_hora_bogota)

    usuario = db.relationship('User', backref='gastos', lazy=True)

    def __init__(self, **kwargs):
        super(Expense, self).__init__(**kwargs)

class PushSubscription(db.Model):
    __tablename__ = 'push_subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    endpoint = db.Column(db.String(500), nullable=False, unique=True)
    p256dh = db.Column(db.String(255), nullable=False)
    auth = db.Column(db.String(255), nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=obtener_hora_bogota)

    usuario = db.relationship('User', backref='suscripciones_push', lazy=True)

    def __init__(self, **kwargs):
        super(PushSubscription, self).__init__(**kwargs)


