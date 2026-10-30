# Interfaces

## 1. Alcance

Este documento define la relacion entre los módulos de escena, cámara y
proyección, aplicación, interfaz y animación. El estado principal de la aplicación es
tridimensional; las coordenadas 2D se generan únicamente al proyectar la escena para
dibujarla.

## 2. Convenciones de coordenadas

### 2.1 Mundo y contenedor

Se utilizan vectores columna y coordenadas homogéneas. Un punto del mundo se representa
como:

```text
p_world = [x, y, z, 1]^T
```

La convención del mundo es:

- Origen `(0, 0, 0)`: esquina inferior izquierda del contenedor.
- `+X`: hacia la derecha.
- `+Y`: hacia arriba.
- `+Z`: hacia el fondo del contenedor.
- Unidad: un cubo unitario tiene dimensiones `1 x 1 x 1`.

El contenedor ocupa:

```text
0 <= x <= 7
0 <= y <= 7
0 <= z <= 6
```

La geometría de objetos se define inicialmente en coordenadas locales y se transforma
al mundo mediante una matriz `M` de tamaño `4 x 4`:

```text
p_world = M @ p_local
```

Las transformaciones rígidas se expresan como:

```text
M = [ R  t ]
    [ 0  1 ]
```

donde `R` es `3 x 3` y `t` es `3 x 1`. Las rotaciones se aplican alrededor del pivote
de cada pieza. La forma recomendada es:

```text
M = T(position) @ T(pivot) @ R @ T(-pivot)
```
todo
¿ `position` representa el origen local de la pieza
o su posición final en el mundo?. Por ahora `position` como la
traslación del origen local después de aplicar la rotación alrededor de `pivot`.

### 2.2 Cámara

La cámara utiliza un sistema 3D propio. Se recomienda que su eje óptico positivo sea
`+Z_camera`, de forma que un punto visible tenga profundidad:

```text
z_camera > 0
```

La transformación mundo-cámara es:

```text
p_camera = [ R_camera | t_camera ] @ p_world
```

con:

```text
t_camera = -R_camera @ C
```

donde `C` es la posición de la cámara expresada en coordenadas del mundo.


### 2.3 Imagen y ventana

La imagen usa la convención habitual de una ventana 2D:

- Origen `(u, v) = (0, 0)` en la esquina superior izquierda.
- `+u`: hacia la derecha.
- `+v`: hacia abajo.
- `u` y `v`: píxeles.
- Ancho de ventana: `width`.
- Alto de ventana: `height`.
- Rango visible: `0 <= u < width`, `0 <= v < height`.

Esta convención no cambia las coordenadas del contenedor. Son sistemas de referencia
distintos:

1. El mundo describe la posición real de los objetos.
2. La cámara transforma el mundo al sistema de observación.
3. La matriz intrínseca transforma coordenadas de cámara a coordenadas homogéneas de
   imagen.
4. La división perspectiva produce coordenadas de imagen.
5. El viewport convierte esas coordenadas al sistema de píxeles de la ventana.

La consecuencia importante es que el eje vertical de la pantalla apunta hacia abajo,
mientras que el eje `+Y` del mundo apunta hacia arriba. La inversión vertical debe
hacerse exactamente una vez. Si la proyección matemática produce una coordenada
`v_up` positiva hacia arriba, el viewport debe usar:

```text
v_screen = height - v_up
```

Si la matriz `K` o la función de proyección ya produce directamente `v` positiva hacia
abajo, el viewport no debe volver a invertirla. Aplicar la conversión dos veces
produciría una imagen reflejada verticalmente.

Esta decisión afecta:

- El signo y la interpretación de la coordenada vertical en `K`.
- El cálculo del punto principal `(c_x, c_y)`.
- El conversor de viewport.
- Las pruebas de coordenadas proyectadas.
- Los errores numéricos de la homografía.
- El dibujo de texto, controles y primitivas 2D.

Todas las comparaciones de proyección y homografía deben hacerse en el mismo sistema
de imagen: `(u, v)` con origen arriba a la izquierda y `v` hacia abajo.

## 3. Cadena de proyección

Para un punto local:

```text
p_image_h = K @ [R_camera | t_camera] @ M @ p_local
```

Dimensiones:

```text
M                    : 4 x 4
[R_camera | t_camera]: 3 x 4
K                    : 3 x 3
p_local              : 4 x 1
p_image_h            : 3 x 1
```

La división perspectiva es:

```text
u = p_image_h[0] / p_image_h[2]
v = p_image_h[1] / p_image_h[2]
```

El código debe validar `p_image_h[2]` antes de dividir. Un punto con profundidad
menor o igual que el plano cercano (`near`) no genera una primitiva dibujable.

La proyección general de 3D a 2D no se denomina homografía. La homografía se reserva
para relacionar imágenes de puntos pertenecientes a un mismo plano mediante una matriz
`3 x 3`.

## 4. Estructuras de datos

### 4.1 Geometría básica

```python
Vertex:
    position: array[3]       # [x, y, z]

Edge:
    start: int
    end: int

Geometry3D:
    vertices: array[N, 3]
    edges: list[Edge]
```

Los índices de las aristas deben referirse a `vertices` y ser válidos. Las caras son
opcionales; la primera versión puede dibujar únicamente aristas.

### 4.2 Pose

```python
Pose:
    position: array[3]       # Traslación en el mundo
    rotation: array[3]       # Ángulos alrededor de X, Y, Z, en radianes
    pivot: array[3]          # Pivote en coordenadas locales
```

La pieza debe conservar su geometría local. Cambiar una pose no debe modificar
permanentemente `local_geometry`.

### 4.3 Pieza

```python
Piece:
    id: str
    display_name: str
    local_geometry: Geometry3D
    pose: Pose
    color: tuple[int, int, int]
    selectable: bool
```

Todas las piezas están formadas por cubos unitarios. Una pieza compuesta debe tener una
sola pose rígida para todos sus cubos.

Piezas requeridas:

| Identificador | Nombre | Tipo |
|---|---|---|
| `L_planar` | L plana | Planaria |
| `Z` | Z | Planaria |
| `square` | Cuadrado | Planaria |
| `T` | T espacial | No planaria |
| `L_nonplanar` | L espacial | No planaria |

Los nombres distinguen explícitamente las dos piezas con forma de L. La planaria y la
no planaria no deben compartir el mismo identificador.

Una pieza es no planaria si sus cubos no están contenidos en un único plano del sistema
local. Esta propiedad debe verificarse en los datos de ejemplo y en las pruebas.

### 4.4 Escena

```python
Scene:
    container: Geometry3D
    pieces: list[Piece]
    selected_piece_id: str | None
    mode: str                  # "interactive", "demo", "victory"
    animation: AnimationState
```

El contenedor y las piezas se almacenan en coordenadas 3D. La escena no debe guardar
coordenadas de pantalla como representación principal.

### 4.5 Cámara

```python
CameraParameters:
    target: array[3]
    azimuth: float              # Radianes
    elevation: float            # Radianes
    distance: float
    focal_length_x: float       # Píxeles
    focal_length_y: float       # Píxeles
    principal_point: array[2]   # [c_x, c_y], píxeles
    near: float
    far: float

Camera:
    intrinsic: array[3, 3]      # K
    rotation: array[3, 3]      # R_camera
    translation: array[3]       # t_camera
    position: array[3]          # C
    parameters: CameraParameters
```

La matriz intrínseca es:

```text
K = [ f_x  0    c_x ]
    [ 0    f_y  c_y ]
    [ 0    0    1   ]
```

### 4.6 Entrada y acciones

```python
Action:
    type: str
    piece_id: str | None
    axis: str | None
    amount: float
```

Tipos mínimos:

```text
select_piece
translate_piece
rotate_piece
orbit_camera
change_camera_distance
change_fov_or_focal_length
reset_camera
reset_piece
start_victory
start_demo
stop_animation
```

La interfaz convierte eventos de teclado o ratón en acciones. El módulo de escena
decide cómo una acción válida modifica la pose; la interfaz no debe modificar vértices
directamente.

### 4.7 Primitivas proyectadas

```python
ProjectedPoint:
    uv: array[2]             # [u, v], píxeles
    depth: float

ProjectedEdge:
    start: ProjectedPoint
    end: ProjectedPoint
    color: tuple[int, int, int]
    source_piece_id: str

DrawPrimitives2D:
    edges: list[ProjectedEdge]
    labels: list[object]
    diagnostics: ProjectionDiagnostics
```

Un punto no proyectable no se representa con coordenadas ficticias. Se devuelve como
`None` o se registra explícitamente como descartado.

### 4.8 Estado de animación

```python
AnimationState:
    name: str | None
    elapsed: float
    duration: float
    running: bool
```

La animación modifica poses 3D y luego ejecuta la misma cadena de transformación y
proyección de la escena interactiva. No se permite animar solamente coordenadas 2D.

## 5. Interfaces públicas

### 5.1 Módulo de geometría

```python
def translation_matrix(tx: float, ty: float, tz: float) -> array[4, 4]:
    """Construye una traslación homogénea."""

def rotation_x(angle: float) -> array[4, 4]:
    """Construye una rotación alrededor de X, en radianes."""

def rotation_y(angle: float) -> array[4, 4]:
    """Construye una rotación alrededor de Y, en radianes."""

def rotation_z(angle: float) -> array[4, 4]:
    """Construye una rotación alrededor de Z, en radianes."""

def compose_pose_matrix(pose: Pose) -> array[4, 4]:
    """Construye M para la pose de una pieza."""
```

Errores:

- Rechazar vectores con dimensión distinta de `3`.
- Rechazar ángulos no finitos.
- Rechazar pivotes o posiciones con `NaN` o infinitos.

### 5.2 Módulo de escena

```python
def create_scene() -> Scene:
    """Crea el contenedor 7 x 7 x 6 y las cinco piezas iniciales."""

def apply_action(scene: Scene, action: Action) -> Scene:
    """Aplica una acción válida sin mutar geometría local."""

def get_geometry(scene: Scene) -> list[tuple[str, Geometry3D]]:
    """Obtiene geometría de contenedor y piezas en coordenadas del mundo."""

def get_piece(scene: Scene, piece_id: str) -> Piece:
    """Obtiene una pieza por identificador."""

def reset_piece(scene: Scene, piece_id: str) -> Scene:
    """Restaura la pose inicial de una pieza."""
```

Reglas:

- `create_scene` debe producir exactamente los identificadores definidos en este
  documento.
- `apply_action` no debe aceptar una pieza inexistente.
- Las traslaciones y rotaciones deben preservar la rigidez.
- Una acción inválida debe producir un error explícito o un resultado diagnosticable;
  no debe convertirse silenciosamente en una acción distinta.
- La escena debe seguir siendo válida después de cada acción.

### 5.3 Módulo de cámara

```python
def build_camera(parameters: CameraParameters) -> Camera:
    """Construye K, R, t y C a partir de los parámetros orbitales."""

def orbit_camera(camera: Camera, delta_azimuth: float,
                 delta_elevation: float) -> Camera:
    """Actualiza la orientación orbital sin modificar la escena."""

def change_camera_distance(camera: Camera, delta: float) -> Camera:
    """Cambia la distancia manteniendo límites positivos."""

def reset_camera() -> Camera:
    """Devuelve la cámara a los parámetros iniciales."""
```

Reglas:

- `distance` debe ser mayor que `near`.
- `near` debe ser positivo.
- `far` debe ser mayor que `near`.
- Los parámetros de la cámara no pueden modificar las coordenadas de la escena.
- La orientación debe ser válida y la cámara debe mirar hacia `target`.

### 5.4 Módulo de proyección

```python
def project_point(point_local: array[3], model: array[4, 4],
                  camera: Camera, viewport: tuple[int, int]
                  ) -> ProjectedPoint | None:
    """Proyecta un punto local al sistema de imagen de la ventana."""

def project_geometry(geometry: Geometry3D, model: array[4, 4],
                     camera: Camera, viewport: tuple[int, int],
                     source_piece_id: str,
                     color: tuple[int, int, int]
                     ) -> DrawPrimitives2D:
    """Proyecta aristas 3D y descarta puntos inválidos."""

def project_scene(scene: Scene, camera: Camera,
                  viewport: tuple[int, int]) -> DrawPrimitives2D:
    """Proyecta contenedor y piezas usando sus poses actuales."""
```

`viewport` se expresa como `(width, height)`. El resultado debe usar coordenadas de
imagen con origen arriba a la izquierda y `v` hacia abajo.

Un punto se descarta cuando:

- Su profundidad es menor o igual que `near`.
- Alguna coordenada proyectada no es finita.
- La transformación contiene dimensiones incompatibles.

El recorte de segmentos puede comenzar descartando una arista si alguno de sus
extremos es inválido. Una versión posterior puede recortar intersecciones con el plano
cercano.

### 5.5 Módulo de homografía

```python
def compute_plane_homography(camera_1: Camera, camera_2: Camera,
                             plane: tuple[array[3], float]
                             ) -> array[3, 3]:
    """Calcula H para puntos del plano entre dos cámaras."""

def apply_homography(H: array[3, 3], uv: array[2]) -> array[2]:
    """Aplica H y normaliza la coordenada homogénea."""

def validate_homography(points_world: array[N, 3],
                        camera_1: Camera, camera_2: Camera,
                        H: array[3, 3]) -> HomographyReport:
    """Compara proyección directa y proyección mediante H."""
```

`plane` debe estar definido con una normal `n` y una constante `d` que cumplan:

```text
n^T @ X + d = 0
```

La homografía solo es válida para puntos del plano especificado. El informe debe
separar los errores de los puntos del plano y los errores de puntos fuera de él.

### 5.6 Módulo de aplicación e interfaz

```python
def event_to_action(event, ui_state) -> Action | None:
    """Convierte una entrada de usuario en una acción."""

def update_application(state, elapsed_seconds: float):
    """Actualiza animación, demostración y estado de la aplicación."""

def draw_frame(primitives: DrawPrimitives2D, ui_state) -> None:
    """Dibuja primitivas y controles 2D."""

def run() -> None:
    """Inicia el ciclo principal de la aplicación."""
```

El ciclo principal debe seguir este orden:

```text
entrada -> acciones -> escena/cámara -> proyección -> dibujo 2D
```

La interfaz puede mostrar diagnósticos, pero no debe reemplazar la escena 3D con
coordenadas dibujadas manualmente.

### 5.7 Módulo de animación

```python
def start_victory(scene: Scene) -> Scene:
    """Inicia la animación de victoria."""

def update_animation(scene: Scene, elapsed_seconds: float) -> Scene:
    """Actualiza poses 3D mediante tiempo transcurrido."""

def start_demo(scene: Scene) -> Scene:
    """Inicia la secuencia determinista de demostración."""

def stop_animation(scene: Scene) -> Scene:
    """Detiene animación o demostración y conserva la escena actual."""
```

La animación debe ser determinista para el mismo tiempo transcurrido. La cámara debe
seguir recibiendo acciones mientras la animación está activa.

## 6. Ejemplo mínimo compartido

El siguiente caso debe ser implementable por todos los módulos:

```python
scene = create_scene()
piece = get_piece(scene, "square")

action = Action(
    type="translate_piece",
    piece_id="square",
    axis="x",
    amount=1.0,
)
scene = apply_action(scene, action)

camera = reset_camera()
primitives = project_scene(scene, camera, viewport=(800, 600))
```

Resultados esperados:

- El contenedor tiene límites `x=0..7`, `y=0..7`, `z=0..6`.
- `square` existe y conserva cuatro cubos unitarios.
- La acción cambia su pose en el eje `X`, no sus vértices locales.
- `camera` se construye con matrices de dimensiones `K: 3 x 3` y
  `[R|t]: 3 x 4`.
- `primitives` contiene aristas 2D o diagnósticos de descarte, nunca coordenadas no
  finitas.
- Las coordenadas de pantalla están expresadas en píxeles con origen arriba a la
  izquierda.

## 7. Responsabilidades y propiedad del estado

| Estado | Módulo responsable | Otros módulos |
|---|---|---|
| Geometría local y poses | Escena | Leen mediante interfaces |
| Selección de pieza | Escena/aplicación | Interfaz solicita cambios mediante acciones |
| Parámetros de cámara | Cámara | Interfaz solicita cambios |
| Coordenadas proyectadas | Proyección | Renderizador las consume |
| Animación | Animación/escena | Aplicación proporciona tiempo |
| Teclas y ratón | Interfaz | Se convierten en acciones |
| Píxeles dibujados | Renderizador | No son estado del mundo |

La proyección debe ser una operación de lectura: no debe modificar piezas, cámara ni
geometría local.

## 8. Criterios de aceptación de la interfaz

- [ ] Se puede crear una escena válida con contenedor `7 x 7 x 6`.
- [ ] Existen `L_planar`, `Z`, `square`, `T` y `L_nonplanar`.
- [ ] Las piezas planarias y no planarias están identificadas sin ambigüedad.
- [ ] Las matrices y vectores tienen las dimensiones documentadas.
- [ ] La escena usa el origen y los ejes acordados.
- [ ] La imagen usa origen arriba a la izquierda y `v` hacia abajo.
- [ ] La inversión vertical se aplica una sola vez.
- [ ] Las acciones modifican poses, no geometría local ni píxeles.
- [ ] La proyección descarta puntos detrás o demasiado cerca de la cámara.
- [ ] La homografía se limita al plano para el que fue calculada.
- [ ] Existe un ejemplo compartido que todos los módulos pueden ejecutar.
- [ ] Los cambios incompatibles de este contrato se documentan y revisan conjuntamente.
