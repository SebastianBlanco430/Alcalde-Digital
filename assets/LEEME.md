# Guía de assets para Blender

Cómo entregar modelos (.glb) y texturas para que el juego los use **editando una sola línea**.
Mientras no haya archivos, el juego dibuja todo con cubos y esferas (modelos procedurales).

## 1. Formato y convenciones

| Tema | Regla |
|---|---|
| Formato | **.glb** (glTF binario). Exportar desde Blender: *File > Export > glTF 2.0*, formato "glTF Binary (.glb)". |
| Unidades | **1 unidad = 1 metro**. Un personaje de pie mide ~1.8 m. |
| Ejes | **+Y arriba** (opción "+Y Up" del exportador). Blender es Z-up; el exportador lo convierte. |
| Origen | En los **pies** (personajes y props) o en el **centro de la base** (edificios). Nunca flotando. |
| Escala | **Aplicada** (`Ctrl+A > Scale`) y rotación aplicada. Escala (1, 1, 1) en el objeto. |
| Frente | El frente del modelo mira hacia **+Z** (en Blender: -Y; el exportador lo rota). Un edificio: su fachada con puerta hacia +Z. |
| Texturas | **PNG**, ancho y alto potencia de 2 (256, 512, 1024, 2048), **máximo 2048 x 2048**. Van en `assets/texturas/<tipo>/`. |
| Nombres | Minúsculas, sin espacios ni tildes: `hospital.glb`, `hospital.png`. **Únicos en todo `assets/`** (el juego cachea por nombre). |
| Materiales | Un material por modelo si se puede (menos llamadas de dibujo). Sin transparencias complicadas. |

### Presupuesto de polígonos (triángulos) sugerido

| Tipo | Triángulos |
|---|---|
| Personaje jugable | 3 000 – 6 000 |
| Peatón | 1 500 – 3 000 |
| Edificio / construcción | 5 000 – 15 000 |
| Prop (árbol, farola, banco) | 300 – 1 500 |

Hay ~7 edificios, ~6 peatones y ~100 props en pantalla a 60 FPS: mejor pocos triángulos y buena textura.

## 2. Carpetas

```
assets/
  modelos/personajes/   rol_ciudadano.glb, peaton.glb ...
  modelos/edificios/    hospital.glb, alcaldia.glb ...
  modelos/props/        arbol.glb, farola.glb, banco.glb, puerta.glb
  texturas/personajes/  (mismos nombres que el modelo, .png)
  texturas/edificios/
  texturas/props/
  terreno/              heightmap.png (opcional, ver sección 5)
```

## 3. Personajes: clips de animación

Armature con huesos y los clips **en el mismo .glb** (Action Editor > "Push Down" y marca *Export Animations*).
El juego pide estas poses; el nombre del clip se configura en el catálogo (nombres por defecto):

| Pose del juego | Clip por defecto | Cuándo |
|---|---|---|
| `parado` | `Idle` | quieto / respirando |
| `caminar` | `Walk` | andar (en bucle) |
| `correr` | `Run` | con Shift (en bucle) |
| `sentado` | `Sit` | en el interior, frente a la computadora |
| `teclear` | `Type` | tecleando (en bucle) |

Si falta un clip el personaje queda en pose estática: **no falla**. El personaje no necesita todos.

## 4. Ejemplo paso a paso: poner el modelo del hospital

1. En Blender: modela el hospital con el origen en el centro de la base, escala aplicada, fachada hacia +Z.
2. Exporta como `hospital.glb` y copia el archivo a `assets/modelos/edificios/hospital.glb`.
3. (Opcional) Copia la textura `hospital.png` a `assets/texturas/edificios/hospital.png`.
4. Abre `frontend/catalogo_assets.py` y cambia **esta línea** del catálogo:

   ```python
   "edificio:Hospital Las Flores": Asset(modelo="modelos/edificios/hospital.glb",
                                         textura="texturas/edificios/hospital.png",
                                         ajustar_a_huella=True, ocultar_puerta=True),
   ```

   - `ajustar_a_huella=True`: el juego escala el modelo a la caja del edificio (14 x 12 x 9 m aprox.). Con `False` se usa la
     escala tal cual (`escala=1.0`) y tú cuidas el tamaño.
   - `ocultar_puerta=True`: el modelo trae su propia puerta; el juego no dibuja la procedural (la puerta lógica y el cartel se
     mantienen, y se abre por código igual).
5. Comprueba sin abrir el juego: `python -m frontend.catalogo_assets --verificar`
   (muestra qué entradas usan modelo propio, cuáles caen al procedural y qué archivos faltan).
6. Abre el juego: `python main.py`. Si el archivo falla, verás **una** advertencia en consola y se usará el modelo procedural.

Claves del catálogo: `rol:ciudadano`, `rol:periodista`, `rol:influencer`, `rol:candidato`, `peaton`,
`edificio:Plaza Central`, `edificio:Alcaldía`, `edificio:Universidad de Ciudad Nova`, `edificio:Parque Municipal`,
`edificio:Barrio Las Flores`, `edificio:Terminal de Buses`, `edificio:Hospital Las Flores`, `edificio_generico`,
`arbol`, `farola`, `banco`, `puerta`.

Otras opciones de `Asset`: `escala`, `rotacion_y` (grados, por si el frente quedó girado), `desplazamiento=(x, y, z)`,
`tinte=(r, g, b)` (multiplica la textura) y `animaciones={"caminar": "MiClip", ...}`.

Un prop (`arbol`, `farola`, `banco`) se carga una vez y se copia en cada lugar. Su origen va en la base.
La `puerta` es la **hoja** (1.6 x 2.4 m aprox., origen en la base al centro de la hoja); el juego la gira sobre la bisagra.

## 5. Terreno de ladera (para quien modela las construcciones del mapa)

El mapa es una **ladera**: cada lugar está sobre una plataforma plana a una cota. Tu edificio debe quedar con su **base a y = 0 local**:
el juego lo coloca a la cota del lugar (`ELEVACION_LUGAR`, en `backend/datos/ciudad_3d.py`).

| Lugar | Cota (m sobre la Alcaldía) |
|---|---|
| Alcaldía | 0.0 (abajo) |
| Plaza Central | 1.5 |
| Terminal de Buses | 3.0 |
| Universidad de Ciudad Nova | 3.5 |
| Parque Municipal | 5.0 |
| Barrio Las Flores | 5.0 |
| Hospital Las Flores | 7.0 (arriba) |

- Para cambiar una cota: edita `ELEVACION_LUGAR`. La pendiente máxima de calle es **15 %**; si una cota la excede, el juego lo avisa al
  arrancar (`ValueError` con la calle y su pendiente).
- Plataforma: cada edificio tiene 1.5 m de terreno plano alrededor de su huella y luego un talud suave de ~8 m. El zócalo del
  edificio procedural baja 1.5 m para tapar el talud; un modelo tuyo puede hacer lo mismo con un "faldón" (la base debe poder
  quedar enterrada ~1 m sin que se note).
- Heightmap opcional: `assets/terreno/heightmap.png` en escala de grises (negro = 0 m, blanco = 10 m, configurable con
  `HEIGHTMAP_METROS`). Si existe, reemplaza la ladera procedural; calles, plazas y edificios siguen a `ELEVACION_LUGAR`.
- Para volver al suelo plano de antes: `TERRENO_ACTIVO = False` en `backend/datos/ciudad_3d.py`.
