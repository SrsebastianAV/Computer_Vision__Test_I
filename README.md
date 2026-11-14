# Jugar

Interfaz Pygame que muestra la proyección perspectiva de una cámara en el centro
de la cara frontal `(3.5, 3.5, 0)`, mirando al centro `(3.5, 3.5, 3)`.

## Ejecutar

Abre **Jugar.py** en la raíz del proyecto y pulsa **Ejecutar archivo Python** en
VS Code. El lanzador utiliza automáticamente `.venv` si existe en esta carpeta.

Desde PowerShell:

```powershell
cd "C:\Users\sseba\OneDrive\Documents\Projects\CV\Computer_Vision__Test_I"
& ".\.venv\Scripts\python.exe" Jugar.py
```

También funciona `python -m src.jugar` con el entorno correcto seleccionado.
Dependencias: `numpy` y `pygame-ce` (este último se importa como `pygame`).
`src.preview` conserva la antigua vista auxiliar; no inicia Jugar.

## Paneles y controles

- **Izquierda:** proyección perspectiva real de los vértices/aristas usando el
  modelo de cámara y las poses actuales de las piezas.
- **Derecha:** escena 3D interactiva ampliada. Muestra contenedor, piezas,
  cámara amarilla y pirámide de visión. No hay punto de prueba ni panel de vistas.
- **1–5:** seleccionan y aíslan una pieza en la derecha mediante el teclado,
  como en preview. La izquierda conserva toda la escena para comprobar su
  proyección. La pieza seleccionada se resalta en ambas vistas.
- **0:** vuelve a mostrar toda la escena a la derecha. **C:** solo contenedor.
- **X / Y / Z:** giran la pieza seleccionada 15 grados alrededor de cada eje.
  **Shift + X / Y / Z:** sentido inverso. Funciona con las cinco piezas.
- **R:** restaura la pose inicial de la pieza seleccionada.
- **A / T / F / S:** cambian el observador de la derecha a vista oblicua,
  superior, frontal o lateral. Son orientaciones de una cámara perspectiva.
- **Arrastrar en la escena / rueda:** orbitan o acercan el observador de la
  derecha, sin mover la cámara que produce la imagen izquierda.
- **Flechas:** orbitan la cámara de proyección alrededor del centro.
- **+ / -:** acercan o alejan esa cámara del objetivo.
- **Inicio (Home):** devuelve la cámara de proyección a `(3.5, 3.5, 0)`.
- **Esc:** cierra la aplicación.
- **F2:** muestra el flujo de un vértice real de la pieza seleccionada
  desde su geometría local hasta píxeles, usando su pose actual.
  F2, Esc o un clic cierran ese panel.

La ventana recalcula los intrínsecos al redimensionarse: mantiene campo vertical
de 60 grados y píxeles cuadrados, ajustando focal y punto principal al recuadro.
Consulta `docs/CAMERA.md` para las fórmulas y convenciones.
`docs/PROJECTION_FLOW.md` explica las clases y cada etapa de la transformación.

Los orígenes son distintos según `INTERFACES.md`: el recuadro de imagen tiene
origen **(u,v)=(0,0) arriba a la izquierda**, con +u a la derecha y +v hacia abajo.
El mundo 3D conserva **(X,Y,Z)=(0,0,0) en la esquina inferior izquierda del
contenedor**, con +Y hacia arriba. Ambos se señalan explícitamente en la interfaz.

## Visibilidad

Los puntos de `z=0` tienen profundidad cero en la posición inicial y se descartan.
Los segmentos que cruzan los planos near/far se recortan antes de la división
perspectiva y las líneas se recortan al panel al dibujarlas. Un punto puede tener
profundidad válida y aun así quedar fuera de la imagen por el campo visual.
La cámara inicial está junto a las piezas: algunas aparecen grandes o cortadas;
alejar la cámara con **-** permite observar más de la escena.

Se dibujan aristas, sin superficies sólidas ni ocultación de líneas traseras.
No hay animación automática ni reglas de juego; Jugar es la interfaz interactiva
para inspeccionar y comprobar las proyecciones.

Pruebas de cámara, proyección e interfaz (sin abrir ventanas):

```powershell
& ".\.venv\Scripts\python.exe" -B -m unittest discover -s tests -p test_camera.py -v
& ".\.venv\Scripts\python.exe" -B -m unittest discover -s tests -p test_projection.py -v
& ".\.venv\Scripts\python.exe" -B -m unittest discover -s tests -p test_jugar.py -v
```
