from decimal import Decimal
from models import db, Sale, Expense, ArqueoCaja, Product

class ArqueoService:
    @staticmethod
    def calcular_totales_dia(ventas_del_dia):
        """Calcula los totales de efectivo y transferencias del día.
        Usa SalePayment si está disponible, de lo contrario usa metodo_pago legacy."""
        total_efectivo = Decimal('0')
        total_transferencia = Decimal('0')
        
        for v in ventas_del_dia:
            if v.pagos:  # Ventas nuevas con tabla sale_payments
                for pago in v.pagos:
                    if pago.metodo_pago == 'efectivo':
                        total_efectivo += Decimal(str(pago.monto))
                    else:  # nequi, bancolombia, daviplata, transferencia
                        total_transferencia += Decimal(str(pago.monto))
            else:  # Retrocompatibilidad con ventas antiguas
                if v.metodo_pago == 'efectivo':
                    total_efectivo += Decimal(str(v.monto_total))
                elif v.metodo_pago in ['transferencia', 'nequi', 'bancolombia', 'daviplata']:
                    total_transferencia += Decimal(str(v.monto_total))
        
        return total_efectivo, total_transferencia

    @staticmethod
    def obtener_resumen_productos(ventas_del_dia):
        resumen_ventas_productos = {}
        for v in ventas_del_dia:
            for detalle in v.detalles:
                nombre = detalle.producto.nombre if detalle.producto else "Producto Eliminado"
                if detalle.variante:
                    nombre = f"{nombre} ({detalle.variante.nombre_variante})"
                
                if nombre not in resumen_ventas_productos:
                    resumen_ventas_productos[nombre] = 0
                resumen_ventas_productos[nombre] += detalle.cantidad_vendida
        return resumen_ventas_productos

    @staticmethod
    def calcular_gastos_automaticos(fecha_seleccionada):
        gastos_diarios_registros = Expense.query.filter(
            db.func.date(Expense.fecha_gasto) == fecha_seleccionada,
            Expense.metodo_pago == 'efectivo'
        ).all()
        return sum(Decimal(str(g.monto)) for g in gastos_diarios_registros)

    @staticmethod
    def calcular_gastos_externos(fecha_seleccionada):
        gastos_externos_registros = Expense.query.filter(
            db.func.date(Expense.fecha_gasto) == fecha_seleccionada,
            Expense.categoria == 'Pago Prod. Externo'
        ).all()
        return sum(Decimal(str(g.monto)) for g in gastos_externos_registros)

    @staticmethod
    def obtener_base_sugerida(fecha_seleccionada):
        ultimo_arqueo = ArqueoCaja.query.filter(ArqueoCaja.fecha_arqueo < fecha_seleccionada).order_by(ArqueoCaja.fecha_arqueo.desc()).first()
        base_sugerida = Decimal('0.0')
        if ultimo_arqueo:
            base_sugerida = Decimal(str(ultimo_arqueo.base_inicial)) + Decimal(str(ultimo_arqueo.total_efectivo_sistema)) - Decimal(str(ultimo_arqueo.gastos_del_dia)) - Decimal(str(ultimo_arqueo.retiro_grueso))
        return base_sugerida
