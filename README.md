# VialSense

VialSense es un prototipo Python para medir el color visible del líquido en imágenes de `vial_fill` con OpenCV, NumPy y pandas. Esta primera versión cubre solo muestras etiquetadas de Recipe 6, Vials 4, 5 y 6.

## Datos disponibles y etiquetas

El README original de Dataset 2 indica que `vial_fill/labels/video5_frame_labels.csv` relaciona cada imagen muestreada con `vial`, `recipe_id` e `in_fill`. El video 5 contiene las únicas etiquetas de receta: recetas 5 a 14. Para empezar, se usa la receta 6; el script acepta cambiar a otra receta individual.

Los datos fuente no forman parte de este proyecto listo para GitHub. El CSV de resultados contiene los nombres de las imágenes y las etiquetas que se usaron. Para repetir las mediciones hacen falta `video5_frame_labels.csv` y las imágenes originales de `vial_fill` en las rutas siguientes:

```
data/raw/vial_fill/images/
data/raw/vial_fill/labels_video5_frame_labels.csv
```

Los resultados y ejemplos anotados incluidos en `outputs/` son derivados pequeños; no se incluyen ZIP, videos ni conjuntos completos de imágenes originales.

## Preparar el entorno

En VS Code abre esta carpeta y selecciona el intérprete `.venv/bin/python`. En la terminal:

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\\Scripts\\activate
python -m pip install -r requirements.txt
```

### Resultados preliminares: Recipe 6

El muestreo actual contiene 5 imágenes del vial 4, 5 del vial 5 y 8 del vial 6. Cada ROI se revisó ampliada individualmente; los cuadros rojos se ubican sobre el líquido visible en la parte inferior de cada vial. Ejecuta:

```bash
PYTHONPATH=src python -m vialsense.analyze_recipe6_manual
```

El script requiere las rutas de etiquetas e imágenes indicadas arriba. El CSV de etiquetas vincula cada fotograma con receta y vial; el script procesa una selección fija de muestras de Recipe 6. Mide el promedio RGB y HSV de la ROI manual. No ejecuta detección automática de vial, contaminación ni umbrales.

Esto genera `outputs/recipe_6_preliminary_measurements.csv`, las 18 imágenes anotadas bajo `outputs/recipe_6_roi_examples/`, mosaicos por vial, y resúmenes descriptivos por vial y combinados en CSV. El rectángulo manual está en `(x1=304, y1=384, x2=328, y2=400)` para las imágenes de cámara 640×480. Las mediciones son promedios directos RGB y HSV de OpenCV sobre todos los píxeles del rectángulo. OpenCV codifica H como 0–179 y S/V como 0–255.

Es una región pequeña elegida para evitar la tapa, la etiqueta, el fondo y el soporte. Aun así, el vidrio, reflejos, baja resolución, iluminación y etapa de llenado pueden afectar los valores. Los 18 cuadros son muestras repetidas de solo tres viales; no permiten definir estadísticamente la variación normal de toda la receta. Las medias RGB observadas fueron: vial 4 (21.65, 26.18, 19.27), vial 5 (35.80, 41.31, 28.61), vial 6 (85.55, 60.99, 26.67). Las medias HSV de OpenCV fueron: vial 4 (56.03, 70.74, 26.20), vial 5 (45.87, 80.73, 41.31), vial 6 (17.51, 176.37, 85.55). Estas diferencias son observaciones para investigar; no se interpretan como contaminación ni normalidad. El resumen combinado es descriptivo, no es un color de referencia validado ni un límite de aceptación. Algunos cuadros borrosos o con vial vacío se dejaron fuera; las tomas no elegidas del vial 5 se omitieron por muestreo y no por fallar una regla. Para integración, `measure_roi` acepta una imagen y coordenadas ROI; otro sistema puede reemplazar las coordenadas manuales por una detección validada.

## Estructura

```
src/vialsense/      carga de etiquetas, medición y comando
data/raw/           ruta local esperada; datos excluidos de Git
outputs/            resultados CSV generados
requirements.txt    dependencias Python
```
