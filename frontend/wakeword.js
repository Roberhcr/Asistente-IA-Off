// ============================================================
// WAKE WORD "Oddye" — usando tu modelo de Teachable Machine
// (model.json + metadata.json en frontend/modelo_voz/)
// ============================================================

const WAKEWORD_RUTA_MODELO = 'Modelo de voz/';

// Nombre EXACTO de tu clase en Teachable Machine (revisa que
// coincida con lo que ves en metadata.json / la app de TM).
const WAKEWORD_ETIQUETA = 'Oddye';

// Qué tan segura tiene que estar la IA (0.0 a 1.0). Si te
// detecta de más, sube este número. Si no te detecta, bájalo.
const WAKEWORD_UMBRAL = 0.85;

let wakewordReconocedor = null;
let wakewordEscuchando = false;
let wakewordProcesando = false;


async function wakewordEmpezarEscucha() {

  if (!wakewordReconocedor) return;

  await wakewordReconocedor.listen((resultado) => {

    if (wakewordProcesando) return;

    const etiquetas = wakewordReconocedor.wordLabels();

    let mejorIndice = 0;

    for (let i = 1; i < resultado.scores.length; i++) {
      if (resultado.scores[i] > resultado.scores[mejorIndice]) {
        mejorIndice = i;
      }
    }

    const nombre = etiquetas[mejorIndice];
    const score = resultado.scores[mejorIndice];

    if (
      nombre.toLowerCase() === WAKEWORD_ETIQUETA.toLowerCase()
      && score >= WAKEWORD_UMBRAL
    ) {
      console.log(`[WakeWord] "${nombre}" detectada (${score.toFixed(2)})`);
      wakewordAlDetectar();
    }

  }, {
    includeSpectrogram: false,
    probabilityThreshold: 0.0, // filtramos nosotros arriba
    overlapFactor: 0.5
  });

  wakewordEscuchando = true;
}


async function wakewordAlDetectar() {

  if (wakewordProcesando) return;
  wakewordProcesando = true;

  try {

    if (wakewordReconocedor && wakewordEscuchando) {
      wakewordReconocedor.stopListening();
      wakewordEscuchando = false;
    }

    await window.pywebview.api.comando_por_voz_detectado();

  } catch (err) {

    console.error('[WakeWord] Error procesando comando:', err);

  } finally {

    wakewordProcesando = false;

    // Reanudar la escucha de "Oddye"
    try {
      await wakewordEmpezarEscucha();
    } catch (err) {
      console.error('[WakeWord] No se pudo reanudar la escucha:', err);
    }
  }
}


async function wakewordIniciar() {

  try {

    const checkpointURL = new URL(
      WAKEWORD_RUTA_MODELO + 'model.json',
      window.location.href
    ).href;

    const metadataURL = new URL(
      WAKEWORD_RUTA_MODELO + 'metadata.json',
      window.location.href
    ).href;

    wakewordReconocedor = speechCommands.create(
      'BROWSER_FFT',
      undefined,
      checkpointURL,
      metadataURL
    );

    await wakewordReconocedor.ensureModelLoaded();

    console.log(
      '[WakeWord] Modelo cargado. Etiquetas:',
      wakewordReconocedor.wordLabels()
    );

    await wakewordEmpezarEscucha();

    console.log('[WakeWord] Escuchando "Oddye"...');

  } catch (err) {

    console.error('[WakeWord] No se pudo iniciar:', err);
  }
}


window.addEventListener('pywebviewready', wakewordIniciar);