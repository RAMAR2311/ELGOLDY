import sys
import os
sys.path.append(os.getcwd())
from app import create_app
from models import db, Product, Receta

app = create_app()
with app.app_context():
    # 1. Encontrar los insumos por nombre usando coincidencias (para evitar problemas de IDs distintos en VPS)
    insumo_pan = Product.query.filter(Product.nombre.ilike('%Pan%')).filter(Product.tipo_producto == 'insumo').first()
    insumo_salchicha = Product.query.filter(Product.nombre.ilike('%Salchicha%')).filter(Product.tipo_producto == 'insumo').first()
    
    # Gaseosa Pequeña (Insumo)
    insumo_gas_peq = Product.query.filter(Product.nombre.ilike('%Gaseosa Peque%')).filter(Product.tipo_producto == 'insumo').first()
    if not insumo_gas_peq:
        insumo_gas_peq = Product.query.filter(Product.nombre.ilike('%Gaseosas%')).filter(Product.tipo_producto == 'insumo').first()
        
    if insumo_gas_peq:
        insumo_gas_peq.nombre = "Gaseosa Pequeña (Insumo)"
    else:
        insumo_gas_peq = Product(
            sku="INS-GAS-PEQ",
            nombre="Gaseosa Pequeña (Insumo)",
            tipo_producto="insumo",
            cantidad_stock=0,
            precio_costo=0.0,
            precio_minimo=0.0,
            precio_sugerido=0.0
        )
        db.session.add(insumo_gas_peq)
    
    # Gaseosa Grande (Insumo)
    insumo_gas_grande = Product.query.filter(Product.nombre.ilike('%Gaseosa Grande%')).filter(Product.tipo_producto == 'insumo').first()
    if not insumo_gas_grande:
        insumo_gas_grande = Product(
            sku="INS-GAS-GDE",
            nombre="Gaseosa Grande (Insumo)",
            tipo_producto="insumo",
            cantidad_stock=0,
            precio_costo=0.0,
            precio_minimo=0.0,
            precio_sugerido=0.0
        )
        db.session.add(insumo_gas_grande)
        
    db.session.commit()
    
    # 2. Buscar Productos Finales por nombre en lugar de ID estático
    prod_sencillo = Product.query.filter(Product.nombre.ilike('%Sencillo%')).filter(Product.tipo_producto != 'insumo').first()
    prod_combo = Product.query.filter(Product.nombre.ilike('%Combo%')).filter(Product.tipo_producto != 'insumo').first()
    prod_gas_peq = Product.query.filter(Product.nombre.ilike('%Gaseosa Peque%')).filter(Product.tipo_producto != 'insumo').first()
    prod_gas_gde = Product.query.filter(Product.nombre.ilike('%Gaseosa Grande%')).filter(Product.tipo_producto != 'insumo').first()
    prod_turno = Product.query.filter(Product.nombre.ilike('%TURNO%')).filter(Product.tipo_producto != 'insumo').first()
    
    final_prods = [p for p in [prod_sencillo, prod_combo, prod_gas_peq, prod_gas_gde, prod_turno] if p]
    final_ids = [p.id for p in final_prods]
    
    # Limpiar recetas anteriores de los productos encontrados
    if final_ids:
        Receta.query.filter(Receta.producto_final_id.in_(final_ids)).delete(synchronize_session=False)
    
    pan_id = insumo_pan.id if insumo_pan else None
    salchicha_id = insumo_salchicha.id if insumo_salchicha else None
    gas_peq_id = insumo_gas_peq.id
    gas_gde_id = insumo_gas_grande.id
    
    # 3. Asignar recetas según instrucciones del usuario
    if prod_sencillo and pan_id and salchicha_id:
        db.session.add(Receta(producto_final_id=prod_sencillo.id, insumo_id=pan_id, cantidad_requerida=1.0))
        db.session.add(Receta(producto_final_id=prod_sencillo.id, insumo_id=salchicha_id, cantidad_requerida=1.0))
    else:
        print("Aviso: No se pudo enlazar 'Hot Dog Sencillo'.")
        
    if prod_combo and pan_id and salchicha_id and gas_peq_id:
        db.session.add(Receta(producto_final_id=prod_combo.id, insumo_id=pan_id, cantidad_requerida=1.0))
        db.session.add(Receta(producto_final_id=prod_combo.id, insumo_id=salchicha_id, cantidad_requerida=1.0))
        db.session.add(Receta(producto_final_id=prod_combo.id, insumo_id=gas_peq_id, cantidad_requerida=1.0))
    else:
        print("Aviso: No se pudo enlazar 'Hot Dog en Combo'.")
        
    if prod_gas_peq and gas_peq_id:
        db.session.add(Receta(producto_final_id=prod_gas_peq.id, insumo_id=gas_peq_id, cantidad_requerida=1.0))
    else:
        print("Aviso: No se pudo enlazar producto final 'Gaseosa Pequeña'.")
        
    if prod_gas_gde and gas_gde_id:
        db.session.add(Receta(producto_final_id=prod_gas_gde.id, insumo_id=gas_gde_id, cantidad_requerida=1.0))
    else:
        print("Aviso: No se pudo enlazar producto final 'Gaseosa Grande'.")
        
    if prod_turno and pan_id and salchicha_id:
        db.session.add(Receta(producto_final_id=prod_turno.id, insumo_id=pan_id, cantidad_requerida=1.0))
        db.session.add(Receta(producto_final_id=prod_turno.id, insumo_id=salchicha_id, cantidad_requerida=1.0))
    else:
        print("Aviso: No se pudo enlazar 'HOG DOG TURNO'.")
    
    db.session.commit()
    print("Las configuraciones de inventario y recetas han sido actualizadas con éxito dinámicamente.")
