# Revisión del código de Oddye (8 de octubre de 2026)

Revisión de `main.py`, `Esclavo/`, `InteligenciaPatron/`, `dictado.py` y `frontend/` contra el documento del proyecto (v3). **No se modificó ningún archivo existente**; solo se agregaron `data/`, `src/`, `reports/`, `tests/`, `README.md`, `requirements-datos.txt`, `.gitignore` y este archivo.

## 1. Errores que afectan el funcionamiento (prioridad alta)

| # | Archivo | Problema | Corrección sugerida |
|---|---|---|---|
| 1 | `frontend/wakeword.js` | `WAKEWORD_ETIQUETA = 'Oddye'`, pero el modelo de Teachable Machine (`Modelo de voz/metadata.json`) tiene las etiquetas `"Class 2", "Class 4", …, "Ruido de fondo"`. **La palabra de activación nunca se dispara.** | Renombrar la clase a "Oddye" en Teachable Machine y volver a exportar, o poner aquí el nombre real de la clase (p. ej. `'Class 2'`). |
| 2 | `Esclavo/acciones_apps.py` → `abrir_app()` | Revisa `comprobacion.get("ok")`, pero `ObservadorPC.comprobar_apertura()` devuelve la clave `"exito"`. **Aunque la app abra, responde "no pude confirmar que se iniciara".** | Cambiar a `comprobacion.get("exito")`. |
| 3 | `Esclavo/acciones_apps.py` → `es_referencia_a_ultima_app()` | Los patrones `\blo\b` y `\bla\b` coinciden con casi cualquier frase («abre **la** carpeta descargas», «apaga **la** computadora»). Si antes se abrió una app, **se abre o cierra esa app en lugar de la carpeta o del comando.** | Aceptar solo pronombres pegados al verbo («ábrelo», «ciérrala») o frases completas («esa app»), no «la»/«lo» sueltos. |
| 4 | `main.py` + `frontend/app.js` | `main.py` llama a `agregarTextoDictado()` y `window.oddyeVozCallback()`, pero **no existen en el frontend**; tampoco hay botón que llame a `iniciar_dictado()`. El dictado en vivo está hecho en el backend pero no conectado. | Definir esas dos funciones en `app.js` y agregar el control de dictado. |
| 5 | `main.py` → `procesar_entrada_usuario()` | Cuando `abrir_app()` falla por el patrón, no se llama a `_manejar_patron_detectado()`; solo ocurre en `simular_fallo_app()`. **En uso real nunca aparece la notificación de ayuda.** | Si `resultado.get("patron", {}).get("detectado")`, llamar a `_manejar_patron_detectado(...)`. |

## 2. Entorno y dependencias

- `requirements.txt` está en **UTF-16** (generado con `pip freeze >` en PowerShell). Guardarlo en UTF-8: `pip freeze | Out-File -Encoding utf8 requirements.txt`.
- Faltan en el `venv` y en `requirements.txt`: **piper-tts** (la voz usa `python -m piper`), **win11toast** (notificaciones), **Pillow** (capturas) y **winshell + pywin32** (papelera). Con el `venv` actual, InteligenciaPatron no carga y la voz falla.
- `webview.start(debug=True)` abre las herramientas de desarrollo: usar `debug=False` para la demo.
- `--cache-type-v q4_0` requiere Flash Attention: agregar `-fa on` al comando de llama-server.
- Hay `ggml-medium.bin` descargado, pero `WHISPER_MODELO` usa `ggml-base.bin`. Decidir cuál se usa y documentarlo (el documento dice *base*).

## 3. Coherencia con el documento

- Mensajes de apagado/reinicio dicen **"Laura, cancela el apagado"**: cambiar a "Oddye".
- `vaciar_papelera` se ejecuta sin confirmación: el documento la marca como acción crítica (`requiere_confirmacion = true`). Agregar confirmación o el mismo margen de cancelación.
- `abrir_explorador` (comandos) duplica la app `archivos`; como `interpretar_apertura()` va primero, el comando nunca se usa.
- `MAPA_APPS` tiene 5 aplicaciones (spotify, word, youtube, netflix, archivos); el dataset usa los mismos identificadores y 11 más (navegador, excel, etc.) para cuando se agreguen. YouTube y Netflix abren páginas web, que requieren Internet.
- `GestorPatrones` solo registra **fallos**. Para RF-09 a RF-16 hay que registrar **todas** las acciones (`registrar_evento("accion", nombre, {...})` después de cada acción correcta).
- En `sugerencias.py`, `INTERVALO_MINIMO = 10 * 25` y `INTERVALO_MAXIMO = 20 * 40` (≈4 y 13 min) parecen errores de escritura de `10 * 60` y `20 * 60`.
- `CEREBROINTEGRADOR.py`, `integracion_patrones.py`, `cerebro_patrones.py` y `respuesta_sugerencia.py` no los usa `main.py`: moverlos a `pruebas/` o borrarlos.
- `memoria_patrones.json` contiene datos de uso reales: no subirlo al repositorio (ya está en `.gitignore`).

## 4. Resultado de evaluar las reglas actuales (`python src/models/evaluar_reglas.py`)

| Métrica | test (143) | test_voz (112) |
|---|---|---|
| Intención correcta en órdenes de acción | 40,4 % | 46,5 % |
| Acción + parámetros correctos | 28,1 % | 32,6 % |
| abrir_aplicacion / ejecutar_comando | 65,0 % / 61,5 % | 80,0 % / 75,0 % |
| abrir_carpeta / cerrar_aplicacion | 15,4 % / 0 % | 16,7 % / 0 % |
| No-acciones que disparan una acción | 15 de 86 (17,4 %) | 10 de 69 (14,5 %) |

Fallos típicos: voseo y usted («abrí», «cerrá», «cierre»), sinónimos («la compu»), apps no registradas y falsas acciones («busca la captura de pantalla» → toma una captura; «crea una rutina que abra Zoom» → abre Zoom).

## 5. Siguiente paso de integración (incremento 5)

En `procesar_entrada_usuario()`, cuando las reglas devuelvan `"chat"`, llamar a `Interprete().interpretar(texto)` de `src/models/predict_model.py` antes de enviar al chat. Si la intención es de acción y el JSON es válido, ejecutar con las mismas funciones de Esclavo (los identificadores ya coinciden). Si es `ambigua`, pedir aclaración. Si es `conversacion_general`, seguir a `enviar_mensaje()`.

Para la sección 15 del informe, con llama-server activo:

```
python src/models/predict_model.py --evaluar test
python src/models/predict_model.py --evaluar test_voz
```
