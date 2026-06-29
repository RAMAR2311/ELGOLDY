import sys
import os
sys.path.append(os.getcwd())
from app import create_app
from models import db, Product, Receta

app = create_app()
with app.app_context():
    # 1. Actualizar el insumo actual de gaseosas
    insumo_gas_peq = Product.query.get(3)
    if insumo_gas_peq:
        insumo_gas_peq.nombre = "Gaseosa Pequeña (Insumo)"
    
    # 2. Crear insumo para gaseosa grande si no existe
    insumo_gas_grande = Product.query.filter_by(nombre="Gaseosa Grande (Insumo)").first()
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
        
    # Limpiar recetas anteriores de los productos mencionados
    Receta.query.filter(Receta.producto_final_id.in_([4, 5, 6, 7, 9])).delete(synchronize_session=False)
    
    # Definir insumos
    pan_id = 1
    salchicha_id = 2
    gas_peq_id = 3
    gas_gde_id = insumo_gas_grande.id
    
    # 3. Asignar recetas según instrucciones del usuario
    # Hot Dog Sencillo (ID 4) -> Pan y Salchicha
    db.session.add(Receta(producto_final_id=4, insumo_id=pan_id, cantidad_requerida=1.0))
    db.session.add(Receta(producto_final_id=4, insumo_id=salchicha_id, cantidad_requerida=1.0))
    
    # Hot Dog en Combo (ID 5) -> Pan, Salchicha, y Gaseosa pequeña
    db.session.add(Receta(producto_final_id=5, insumo_id=pan_id, cantidad_requerida=1.0))
    db.session.add(Receta(producto_final_id=5, insumo_id=salchicha_id, cantidad_requerida=1.0))
    db.session.add(Receta(producto_final_id=5, insumo_id=gas_peq_id, cantidad_requerida=1.0))
    
    # Gaseosa Pequeña (ID 6) -> Gaseosa pequeña
    db.session.add(Receta(producto_final_id=6, insumo_id=gas_peq_id, cantidad_requerida=1.0))
    
    # Gaseosa Grande (ID 7) -> Gaseosa grande
    db.session.add(Receta(producto_final_id=7, insumo_id=gas_gde_id, cantidad_requerida=1.0))
    
    # HOG DOG TURNO (ID 9) -> Pan y Salchicha
    db.session.add(Receta(producto_final_id=9, insumo_id=pan_id, cantidad_requerida=1.0))
    db.session.add(Receta(producto_final_id=9, insumo_id=salchicha_id, cantidad_requerida=1.0))
    
    db.session.commit()
    print("Las configuraciones de inventario y recetas han sido actualizadas con éxito.")
