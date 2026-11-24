# Contrato interno del final animado (`frontend/final_animado/`)

Sesión C (2026-11-23). Tres piezas trabajan a la vez; este archivo fija quién escribe qué y cómo se hablan.
Guion plano por plano: `sesiones-24nov\final\guion.md`. Datos: `backend/datos/finales_historia.json` → `animacion`.

## Archivos y dueños

| Archivo | Dueño | Qué es |
|---|---|---|
| `__init__.py` | orquestador | Bandera `activo()` (`ALCALDE_FINAL_ANIMADO`, encendida por defecto). No se toca. |
| `lugares.py` | orquestador → `decorado-actores` | Anclas (`anclas(mundo)`, `a_mundo`, `en_suelo`). `decorado-actores` puede **correr** un ancla si choca; nunca renombrarla ni cambiar la convención. |
| `contrato.md` | orquestador | Este archivo. |
| `_calculos.py` | `director-final` | PURO. Guion → planos, tiempos, subtítulos, mantener para saltar, curvas. |
| `camaras.py` | `director-final` | PURO. Tomas de cámara por `id` de plano, relativas a las anclas. |
| `director.py` | `director-final` | Ursina. Cámara, HUD, fundidos, subtítulos, saltar, audio, respaldo. |
| `puesta.py` | `decorado-actores` | PURO. Qué decorado y actores lleva cada plano (posiciones relativas a anclas, poses). |
| `escenografia.py` (+ los módulos que necesite: `decorado.py`, `actores.py`, `ciudad.py`, `poses_final.py`…) | `decorado-actores` | Ursina. Estado forzado de la ciudad, decorado, actores, limpieza. |
| `backend/datos/finales_historia.json` (`animacion`) | orquestador (guion-textos) | Ids, duraciones, anclas y subtítulos. **Los subagentes no lo editan**: si un plano necesita otra duración u otro id, se pide al orquestador en el `informe.md`. |

Tests (en `tests/`, local): `test_final_animado_calculos.py`, `test_final_animado_camaras.py`, `test_final_animado_registro.py`
(director-final); `test_final_animado_puesta.py` (decorado-actores); `test_final_animado_lugares.py`, `test_final_animado_datos.py` (orquestador).

## Convenciones comunes

- Rumbo en grados: `0 = +z`, `90 = +x` (`math.atan2(dx, dz)`), como `Personaje.fijar_rumbo`.
- Marco local de un ancla: `(derecha, alto, frente)`; `frente` = hacia donde mira el sujeto. `lugares.a_mundo(ancla, d, a, f)`.
- Ids de plano: los del JSON (`m1_reelegido`, `b6_podio`, `n4_periodista`…). El prefijo es el final (`m`/`b`/`n`).
- Nada de esto importa `ursina` en `_calculos.py`, `camaras.py`, `puesta.py`, `lugares.py`.
- Todo lo que se crea en el mundo cuelga de **una raíz 3D** que da el director (`raiz3d`, hija de `scene`); todo lo de pantalla, de una raíz UI del director. `limpiar()` las destruye. Nada queda en `scene` ni en `camera.ui` al terminar.
- Ninguna función pública lanza hacia el juego: el director envuelve cada llamada; un fallo = respaldo a las viñetas.
- No se apaga ni se atenúa ningún efecto (tinta, cel, niebla, pase final, MSAA, luz de noche).

## `_calculos.py` (director-final) — lo que consumen los demás

```python
@dataclass(frozen=True)
class Plano:
    id: str            # "b6_podio", "m4_periodista"...
    final: str         # "bueno" | "neutro" | "malo"
    ancla: str         # nombre en lugares.anclas()
    segundos: float
    subtitulos: tuple  # (str, ...) ya cortos
    rol: str | None    # rol del plano propio; None en los comunes
    indice: int        # posición en la secuencia

def cargar_guion(datos=None) -> dict                 # la sección «animacion» (por defecto, la del JSON del juego)
def planos_de(final, roles, guion=None) -> list[Plano]
    # roles: roles presentes en la partida, en orden de turno (["ciudadano"], o varios en local).
    # El hueco {"rol": true} se cambia por el plano de cada rol presente («segundos_rol»: solo / varios).
    # Sin roles válidos: el del ciudadano.
def estado_ciudad(final, guion=None) -> dict         # {"etapa": -3|0|3, "hora": float, "musica": str|None, "sonido": str|None}
```

## `escenografia.py` (decorado-actores) — lo que llama el director

```python
class Escenografia:
    def __init__(self, escena, raiz3d, conexion=None): ...
        # escena: EscenaMundo. raiz3d: Entity hija de `scene` creada por el director. conexion: ConexionFlujo (para
        # conexion.etapas_final, conexion.vigia_reloj...). No hace nada costoso aquí.

    def preparar(self, final, roles, planos):
        """Con la pantalla YA EN NEGRO. Fuerza el estado de la ciudad del final (etapa −3/0/+3, hora fija, sin peatones,
        NPC, globos ni avatares del juego a la vista; las capas de ciudad_viva sí: fuego, banderines, fiesta) y crea TODO
        el decorado y los actores de `planos`, ocultos. Puede tardar (la carga está tapada). Lanza si no puede."""

    def entrar(self, plano):
        """Corte al plano: enciende su decorado y sus actores (pose inicial) y apaga los de los demás. Barato (< 5 ms):
        solo `enabled` y colocar. Se llama con la pantalla en negro o en el corte."""

    def avanzar(self, plano, t, dt):
        """Cada frame del plano. `t` = 0..1 (progreso del plano), `dt` en s. Anima actores y decorado (subir al podio,
        luces que se apagan, pancartas, aplausos...). Barato: sin crear ni destruir entidades."""

    def limpiar(self):
        """Destruye lo creado y DEVUELVE la ciudad como estaba (etapa, hora, peatones, NPC, avatares). Idempotente,
        nunca lanza. Se llama al terminar, al saltar y si algo falla."""
```

El director llama, en este orden: fundido a negro → `preparar` → (por plano) `entrar` + cámara → fundido de vuelta →
`avanzar` cada frame → … → fundido a negro → `limpiar` → `al_terminar()` → el panel final aparece ya con el juego limpio.

La cámara la pone **solo** el director (`camaras.py`). La escenografía no toca `camera` ni el HUD.
La escenografía es quien esconde y devuelve lo que vive en `scene` (peatones, NPC de ambiente y de etapa, globos, avatares,
vehículos, marcadores de misión); el director esconde y devuelve lo de `camera.ui` (HUD, avisos, medidor) y `escena._cinematica`.

## `camaras.py` (director-final) — lo que mira decorado-actores

```python
def toma(plano_id, anclas, mundo) -> Toma      # puntos clave ya en coordenadas del mundo
def camara_en(toma, t) -> (posicion, mira, fov) # t = 0..1 del plano
```
`decorado-actores` puede importar `camaras` para sus capturas de prueba; si aún no existe, usa una cámara de prueba
propia a ~8 m del ancla, 2,5 m de alto, mirando al ancla desde su frente. **El encuadre de cada plano está descrito en el
guion**: cada uno coloca lo suyo respecto del ancla tal como dice allí, y así casan sin esperarse.

## `director.py` (director-final) — lo que llama el juego

```python
def crear_final_animado(escena, final, roles, al_terminar, al_fallo, conexion=None, guardia=None, escala=1.0):
    """Crea y arranca el final animado. `al_terminar(saltada: bool)` UNA vez, con todo limpio. `al_fallo(error)` UNA vez,
    con todo limpio, si algo lanzó al cargar o en un frame (el registro abre entonces las viñetas). Lanza si no se puede
    ni construir (ya limpio). `escala` multiplica las duraciones (pruebas)."""
```
Devuelve la entidad (con `.terminada`, `.saltar()`, `.plano_actual`, `.tiempo`, `.duracion_total`).

## Enganche en el juego (director-final)

`frontend/registro_reloj.py::_cinematica_del_final`: con `final_animado.activo()` y final en (`bueno`, `neutro`, `malo`)
lanza `crear_final_animado`; si falla (al crear o por `al_fallo`) lanza las viñetas de `cinematica_final` (bueno / malo;
el neutro no tiene viñetas: va directo al panel). Con la bandera en 0, exactamente lo de `0b7e148`. El panel final sale
siempre.
