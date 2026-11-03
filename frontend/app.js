const chat = document.getElementById('chat');
const emptyState = document.getElementById('emptyState');
const input = document.getElementById('input');
const sendBtn = document.getElementById('sendBtn');
const status = document.getElementById('status');
const statusText = document.getElementById('statusText');
const brainBtn = document.getElementById('brainBtn');
const voiceOutBtn = document.getElementById('voiceOutBtn');
const micBtn = document.getElementById('micBtn');

let cerebroListo = false;
let grabando = false;
let contadorActual = null;   // el cronómetro "0.0s" mientras piensa
let hablando = false;        // Oddye está diciendo algo en voz alta

// Dictado en vivo
let dictando = false;            // escuchando y escribiendo en la barra
let dictadoTerminando = false;   // ya se detuvo, esperando las últimas palabras
let textoDictado = false;        // la barra tiene texto dictado sin enviar
let temporizadorDictado = null;

function addMessage(texto, tipo) {
  if (emptyState) emptyState.remove();

  const wrapper = document.createElement('div');
  wrapper.className = `msg-row ${tipo}`;

  if (tipo === 'ai') {
    const avatar = document.createElement('span');
    avatar.className = 'ai-avatar';
    wrapper.appendChild(avatar);
  }

  const bubble = document.createElement('div');
  bubble.className = `msg ${tipo}`;
  bubble.textContent = texto;
  wrapper.appendChild(bubble);

  // Botón copiar solamente para las respuestas de la IA
  if (tipo === 'ai') {
    const copyBtn = document.createElement('button');
    copyBtn.className = 'copy-btn';
    copyBtn.title = 'Copiar respuesta';
    copyBtn.textContent = '📋';

    copyBtn.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(bubble.textContent);

        copyBtn.textContent = '✓';
        copyBtn.title = 'Copiado';

        setTimeout(() => {
          copyBtn.textContent = '📋';
          copyBtn.title = 'Copiar respuesta';
        }, 1500);

      } catch (err) {
        console.error('No se pudo copiar:', err);
      }
    });

    wrapper.appendChild(copyBtn);
  }

  chat.appendChild(wrapper);
  chat.scrollTop = chat.scrollHeight;

  return bubble;
}

function addContador() {
  if (emptyState) emptyState.remove();

  const wrapper = document.createElement('div');
  wrapper.className = 'msg-row ai';

  const avatar = document.createElement('span');
  avatar.className = 'ai-avatar';
  wrapper.appendChild(avatar);

  const bubble = document.createElement('div');
  bubble.className = 'msg ai contador';
  bubble.textContent = '0.0s';
  wrapper.appendChild(bubble);

  chat.appendChild(wrapper);
  chat.scrollTop = chat.scrollHeight;

  const inicio = performance.now();

  const intervalo = setInterval(() => {
    const segundos = ((performance.now() - inicio) / 1000).toFixed(1);
    bubble.textContent = segundos + 's';
  }, 100);

  return {
    detener: () => clearInterval(intervalo),
    quitar: () => wrapper.remove(),
  };
}

function setEstado(texto, pensando) {
  statusText.textContent = texto;
  status.classList.toggle('thinking', !!pensando);
}

async function encenderCerebro() {
  setEstado('encendiendo cerebro...', true);

  input.disabled = true;
  sendBtn.disabled = true;
  brainBtn.disabled = true;
  voiceOutBtn.disabled = true;
  micBtn.disabled = true;

  try {
    const resultado = await window.pywebview.api.cargar_modelo();

    if (resultado.ok) {
      cerebroListo = true;
      setEstado('lista', false);

      input.disabled = false;
      sendBtn.disabled = false;
      brainBtn.disabled = false;
      voiceOutBtn.disabled = false;
      micBtn.disabled = false;

      input.focus();

    } else {
      setEstado('error al encender', false);
      addMessage(
        resultado.mensaje || 'No se pudo encender el cerebro.',
        'ai'
      );
    }

  } catch (err) {
    setEstado('error al encender', false);
    console.error(err);
  }
}


// ============================================================
// ENVÍO DE MENSAJES
// ============================================================

async function enviar() {

  // Si todavía hay una respuesta en curso, se detiene primero y
  // después se envía lo nuevo (así puedes interrumpirla).
  if (enviando && input.value.trim()) {

    await cancelar();

    for (let i = 0; i < 60 && enviando; i++) {
      await new Promise((r) => setTimeout(r, 50));
    }

    if (enviando) return;
  }

  // Si todavía se está dictando, el primer envío solo detiene el dictado
  // para que el texto quede completo. Luego se envía con otro Enter.
  if (dictando || dictadoTerminando) {
    if (dictando) detenerDictado();
    return;
  }

  let texto = input.value.trim();

  if (!texto || !cerebroListo) return;

  // Si el texto vino del dictado, Qwen quita las autocorrecciones
  // ("abre Chrome, no, abre Word" -> "abre Word") antes de enviarlo.
  if (textoDictado) {

    textoDictado = false;

    try {

      sendBtn.disabled = true;
      setEstado('revisando texto...', true);

      const limpio =
        await window.pywebview.api.limpiar_dictado(texto);

      if (limpio && limpio.trim()) {
        texto = limpio.trim();
      }

    } catch (err) {
      console.error('No se pudo limpiar el dictado:', err);
    }
  }

  addMessage(texto, 'user');

  input.value = '';
  autoResize();

  setEstado('pensando...', true);

  enviando = true;
  actualizarBotonEnviar();

  const contador = addContador();
  contadorActual = contador;

  try {

    // IMPORTANTE:
    // Ahora la entrada pasa por procesar_entrada_usuario().
    // Esto permite que Esclavo pueda detectar y ejecutar
    // acciones como abrir Word, Spotify, carpetas, etc.
    const resultado =
      await window.pywebview.api.procesar_entrada_usuario(texto);

    if (resultado && resultado.chat_id) {
      chatActivoId = resultado.chat_id;
    }

    refrescarChats();

    contador.detener();
    contador.quitar();

    setEstado('lista', false);

    if (resultado && (resultado.ya_mostrada || resultado.cancelada)) {
      // El texto ya fue apareciendo (o la respuesta se detuvo).
    } else if (resultado && resultado.respuesta) {
      addMessage(resultado.respuesta, 'ai');
    } else {
      addMessage('La acción fue procesada.', 'ai');
    }

  } catch (err) {

    contador.detener();
    contador.quitar();

    setEstado('lista', false);

    addMessage(
      'Ocurrió un error al conectar con el modelo.',
      'ai'
    );

    console.error(err);

  } finally {

    enviando = false;

    sendBtn.disabled = false;
    actualizarBotonEnviar();
    input.focus();

  }
}


function autoResize() {
  input.style.height = 'auto';
  input.style.height =
    Math.min(input.scrollHeight, 160) + 'px';

  try {
    actualizarBotonEnviar();
  } catch (err) { /* aún no está lista la página */ }
}


// ============================================================
// BOTÓN ENVIAR
// ============================================================

const ICONO_ENVIAR = sendBtn.innerHTML;

const ICONO_DETENER =
  '<svg viewBox="0 0 24 24" width="18" height="18" fill="none">' +
  '<rect x="6.5" y="6.5" width="11" height="11" rx="2" ' +
  'fill="currentColor"/></svg>';

function actualizarBotonEnviar() {

  const ocupado = enviando || hablando;
  const hayTexto = input.value.trim().length > 0;
  const detener = ocupado && !hayTexto;

  sendBtn.classList.toggle('detener', detener);

  sendBtn.title = detener ? 'Detener (Esc)' : 'Enviar';

  const icono = detener ? ICONO_DETENER : ICONO_ENVIAR;

  if (sendBtn.dataset.icono !== (detener ? 'detener' : 'enviar')) {
    sendBtn.innerHTML = icono;
    sendBtn.dataset.icono = detener ? 'detener' : 'enviar';
  }

}

async function cancelar() {

  try {
    await window.pywebview.api.cancelar_respuesta();
  } catch (err) {
    console.error('No se pudo detener:', err);
  }

}

// Oddye avisa cuándo empieza y cuándo termina de hablar.
window.oddyeVozCallback = function (evento) {

  if (evento === 'iniciando' || evento === 'hablando') {
    hablando = true;
  } else if (evento === 'terminado' || evento === 'error') {
    hablando = false;
  }

  actualizarBotonEnviar();

};

sendBtn.addEventListener('click', () => {

  if ((enviando || hablando) && !input.value.trim()) {
    cancelar();
    return;
  }

  enviar();

});

document.addEventListener('keydown', (e) => {

  if (e.key === 'Escape' && (enviando || hablando)) {
    e.preventDefault();
    cancelar();
  }

});


// ============================================================
// ENTER PARA ENVIAR
// ============================================================

input.addEventListener('keydown', (e) => {

  if (e.key === 'Enter' && !e.shiftKey) {

    e.preventDefault();

    enviar();

  }

});


input.addEventListener('input', autoResize);


// ============================================================
// MODO PENSAMIENTO
// ============================================================

brainBtn.addEventListener('click', async () => {

  const resultado =
    await window.pywebview.api.alternar_pensamiento();

  brainBtn.classList.toggle(
    'active',
    resultado.activo
  );

});


// ============================================================
// MODO VOZ
// ============================================================

voiceOutBtn.addEventListener('click', async () => {

  const resultado =
    await window.pywebview.api.alternar_voz();

  voiceOutBtn.classList.toggle(
    'active',
    resultado.activo
  );

});


// ============================================================
// MICRÓFONO (modo antiguo: mantener presionado)
// Estas funciones se conservan, pero ya no están conectadas al
// botón: ahora el botón hace dictado en vivo (más abajo).
// ============================================================

async function iniciarGrabacion() {

  if (grabando || !cerebroListo) return;

  grabando = true;

  micBtn.classList.add('recording');

  setEstado('escuchando...', true);

  try {

    const resultado =
      await window.pywebview.api.iniciar_grabacion();

    if (!resultado.ok) {

      grabando = false;

      micBtn.classList.remove('recording');

      setEstado('lista', false);

      addMessage(
        resultado.mensaje ||
        'No se pudo iniciar la grabación.',
        'ai'
      );

    }

  } catch (err) {

    grabando = false;

    micBtn.classList.remove('recording');

    setEstado('lista', false);

    console.error(err);

  }
}


async function detenerGrabacion() {

  if (!grabando) return;

  grabando = false;

  micBtn.classList.remove('recording');

  input.disabled = true;
  sendBtn.disabled = true;

  setEstado('transcribiendo...', true);

  try {

    const resultado =
      await window.pywebview.api.detener_grabacion_y_transcribir();

    if (resultado.ok && resultado.texto) {

      input.value = resultado.texto;

      input.disabled = false;
      sendBtn.disabled = false;

      setEstado('lista', false);

      // IMPORTANTE:
      // enviar() utilizará procesar_entrada_usuario(),
      // por lo que posteriormente la voz también podrá
      // utilizar Esclavo.
      await enviar();

      return;

    } else {

      setEstado('lista', false);

      addMessage(
        resultado.mensaje ||
        'No pude entender el audio.',
        'ai'
      );

    }

  } catch (err) {

    setEstado('lista', false);

    console.error(err);

  }

  input.disabled = false;
  sendBtn.disabled = false;
}


// ============================================================
// DICTADO EN VIVO
// Clic en el micrófono = empieza a dictar. Las frases van
// apareciendo en la barra mientras hablas. Se detiene solo tras
// unos segundos de silencio (o con otro clic) y el texto queda
// fijo en la barra para editarlo antes de enviar.
// ============================================================

function finalizarDictadoUI() {

  dictando = false;
  dictadoTerminando = false;

  clearTimeout(temporizadorDictado);

  micBtn.classList.remove('recording');

  setEstado('lista', false);

  input.focus();

  const fin = input.value.length;
  input.setSelectionRange(fin, fin);
}


// Python llama a esta función con cada frase transcrita.
window.agregarTextoDictado = function (texto) {

  if (!texto) return;

  const actual = input.value;
  const separador = actual && !/\s$/.test(actual) ? ' ' : '';

  input.value = actual + separador + texto;

  textoDictado = true;

  autoResize();

  input.scrollTop = input.scrollHeight;
};


// Python avisa que se detuvo por silencio (falta la última frase).
window.dictadoDeteniendoPorSilencio = function () {

  if (!dictando) return;

  dictadoTerminando = true;

  micBtn.classList.remove('recording');

  setEstado('terminando...', true);
};


// Python avisa que ya escribió todo el texto.
window.dictadoTerminado = function () {
  finalizarDictadoUI();
};


async function iniciarDictado() {

  if (dictando || dictadoTerminando || !cerebroListo) return;

  try {

    const resultado =
      await window.pywebview.api.iniciar_dictado();

    if (resultado && resultado.ok) {

      dictando = true;

      micBtn.classList.add('recording');

      setEstado('escuchando...', true);

    } else {

      addMessage(
        (resultado && resultado.mensaje) ||
        'No se pudo iniciar el dictado.',
        'ai'
      );
    }

  } catch (err) {

    console.error(err);
  }
}


async function detenerDictado() {

  if (!dictando || dictadoTerminando) return;

  dictadoTerminando = true;

  micBtn.classList.remove('recording');

  setEstado('terminando...', true);

  // Respaldo: si Python no avisa, se libera la interfaz.
  temporizadorDictado = setTimeout(finalizarDictadoUI, 20000);

  try {

    await window.pywebview.api.detener_dictado();

  } catch (err) {

    console.error(err);

    finalizarDictadoUI();
  }
}


micBtn.addEventListener('click', () => {

  if (dictando) {
    detenerDictado();
  } else {
    iniciarDictado();
  }

});


// ============================================================
// PYWEBVIEW
// ============================================================

// Esperar a que pywebview esté listo
// y encender el cerebro.
window.addEventListener(
  'pywebviewready',
  encenderCerebro
);


// ============================================================
// INTELIGENCIA PATRÓN
// Mensajes enviados desde Python
// ============================================================

window.mostrarMensajeExterno = function (texto, tipo) {

  addMessage(
    texto,
    tipo || 'ai'
  );

  refrescarChatsSuave();

};


window.setEstadoExterno = function (texto, pensando) {

  setEstado(
    texto,
    !!pensando
  );

};


// ============================================================
// TEXTO AL UNÍSONO CON LA VOZ
// Python avisa cada vez que empieza a sonar una frase; aquí sus
// palabras van apareciendo repartidas durante lo que dura el audio.
// ============================================================

let streamBubble = null;
let streamTemporizadores = [];

function iniciarMensajeStream() {

  if (streamBubble) return;

  if (contadorActual) {
    contadorActual.detener();
    contadorActual.quitar();
    contadorActual = null;
  }

  streamBubble = addMessage('', 'ai');
  streamBubble.classList.add('escribiendo');

}

window.agregarTextoStream = function (texto, duracionSeg) {

  iniciarMensajeStream();

  const palabras = (texto || '').split(/\s+/).filter(Boolean);

  if (!palabras.length) return;

  const bubble = streamBubble;

  const pesos = palabras.map((p) => p.length + 1);
  const total = pesos.reduce((a, b) => a + b, 0);

  // Las palabras terminan de salir un poco antes que el audio.
  const duracionMs = Math.max(200, (duracionSeg || 1) * 1000 * 0.9);

  let acumulado = 0;

  palabras.forEach((palabra, i) => {

    const cuando = (acumulado / total) * duracionMs;

    acumulado += pesos[i];

    const t = setTimeout(() => {

      if (streamBubble !== bubble) return;

      bubble.textContent +=
        (bubble.textContent ? ' ' : '') + palabra;

      chat.scrollTop = chat.scrollHeight;

    }, cuando);

    streamTemporizadores.push(t);

  });

};

function limpiarStream() {

  streamTemporizadores.forEach(clearTimeout);
  streamTemporizadores = [];

}

window.finalizarMensajeStream = function (textoFinal) {

  limpiarStream();

  if (streamBubble) {

    if (textoFinal) streamBubble.textContent = textoFinal;

    streamBubble.classList.remove('escribiendo');

  } else if (textoFinal) {

    if (contadorActual) {
      contadorActual.detener();
      contadorActual.quitar();
      contadorActual = null;
    }

    addMessage(textoFinal, 'ai');

  }

  streamBubble = null;

  chat.scrollTop = chat.scrollHeight;

  refrescarChatsSuave();

};

// Sin voz: el texto llega a trozos mientras Qwen lo genera.
window.agregarTextoVivo = function (trozo) {

  iniciarMensajeStream();

  streamBubble.textContent += trozo;

  chat.scrollTop = chat.scrollHeight;

};

// La respuesta se detuvo: queda lo que ya se había mostrado.
window.cancelarMensajeStream = function () {

  limpiarStream();

  if (streamBubble) {

    streamBubble.classList.remove('escribiendo');

    if (streamBubble.textContent.trim()) {
      streamBubble.classList.add('cortado');
    } else if (streamBubble.parentElement) {
      streamBubble.parentElement.remove();
    }

  }

  streamBubble = null;

  refrescarChatsSuave();

};

window.descartarMensajeStream = function () {

  limpiarStream();

  if (streamBubble && streamBubble.parentElement) {
    streamBubble.parentElement.remove();
  }

  streamBubble = null;

};


// ============================================================
// ESCUCHA POR NOMBRE (tipo Alexa)
// Python mantiene el micrófono atento; aquí solo está el botón
// que la enciende o la apaga y el aviso de su estado.
// ============================================================

const listenBtn = document.getElementById('listenBtn');

window.setEscuchaExterna = function (activa) {

  listenBtn.classList.toggle('active', !!activa);

  listenBtn.title = activa
    ? 'Escuchando: di "Oddye" (clic para apagar)'
    : 'Escucha por nombre apagada (clic para encender)';

};

listenBtn.addEventListener('click', async () => {

  listenBtn.disabled = true;

  try {

    const r = await window.pywebview.api.alternar_escucha();

    window.setEscuchaExterna(!!r.activo);

    if (!r.ok && r.mensaje) {
      addMessage(r.mensaje, 'ai');
    }

  } catch (e) {
    console.error('[Escucha]', e);
  } finally {
    listenBtn.disabled = false;
  }

});

window.addEventListener('pywebviewready', async () => {

  try {

    const r = await window.pywebview.api.estado_escucha();

    listenBtn.style.display = r.disponible ? '' : 'none';

    window.setEscuchaExterna(!!r.activo);

  } catch (e) {}

});


// ============================================================
// BARRA LATERAL DE CHATS
// Cada conversación se guarda en Python (carpeta Chats/). Al abrir
// uno, Python le devuelve el historial a Qwen y se puede seguir
// conversando donde se quedó.
// ============================================================

const layout = document.getElementById('layout');
const chatList = document.getElementById('chatList');
const chatSearch = document.getElementById('chatSearch');
const newChatBtn = document.getElementById('newChatBtn');
const sidebarToggle = document.getElementById('sidebarToggle');

let chatActivoId = null;       // chat abierto ahora (null = chat nuevo)
let enviando = false;          // hay un mensaje en curso
let temporizadorBusqueda = null;
let temporizadorRefresco = null;
let temporizadorBorrar = null;


function chatsApi() {
  return window.pywebview && window.pywebview.api;
}


// ---------- agrupar por fecha ----------

function nombreGrupo(segundos) {

  const fecha = new Date(segundos * 1000);
  const ahora = new Date();

  const inicioHoy = new Date(
    ahora.getFullYear(), ahora.getMonth(), ahora.getDate()
  ).getTime();

  const dia = 24 * 60 * 60 * 1000;

  const t = fecha.getTime();

  if (t >= inicioHoy) return 'Hoy';
  if (t >= inicioHoy - dia) return 'Ayer';
  if (t >= inicioHoy - 7 * dia) return 'Últimos 7 días';
  if (t >= inicioHoy - 30 * dia) return 'Últimos 30 días';

  return 'Más antiguos';
}


// ---------- dibujar la lista ----------

function iconoSvg(ruta) {
  return (
    '<svg viewBox="0 0 24 24" width="14" height="14" fill="none">' +
    ruta +
    '</svg>'
  );
}

const ICONO_EDITAR = iconoSvg(
  '<path d="M4 20h4L19 9l-4-4L4 16v4Z" stroke="currentColor" ' +
  'stroke-width="1.5" stroke-linejoin="round"/>'
);

const ICONO_BORRAR = iconoSvg(
  '<path d="M5 7h14M10 7V5h4v2M7 7l1 12h8l1-12" stroke="currentColor" ' +
  'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
);


function dibujarChats(lista, activo) {

  chatList.innerHTML = '';

  if (!lista || lista.length === 0) {

    const vacio = document.createElement('div');
    vacio.className = 'chat-list-empty';

    vacio.textContent = chatSearch.value.trim()
      ? 'No encontré chats con eso.'
      : 'Aún no hay chats guardados. Escribe algo y aparecerá aquí.';

    chatList.appendChild(vacio);

    return;
  }

  let grupoActual = null;

  lista.forEach((chatInfo) => {

    const grupo = nombreGrupo(chatInfo.actualizado);

    if (grupo !== grupoActual) {

      grupoActual = grupo;

      const titulo = document.createElement('div');
      titulo.className = 'chat-group-title';
      titulo.textContent = grupo;

      chatList.appendChild(titulo);
    }

    chatList.appendChild(crearItemChat(chatInfo, chatInfo.id === activo));
  });
}


function crearItemChat(chatInfo, activo) {

  const item = document.createElement('div');
  item.className = 'chat-item' + (activo ? ' active' : '');
  item.dataset.id = chatInfo.id;
  item.title = chatInfo.titulo;

  const titulo = document.createElement('span');
  titulo.className = 'chat-item-title';
  titulo.textContent = chatInfo.titulo;
  item.appendChild(titulo);

  const acciones = document.createElement('span');
  acciones.className = 'chat-item-actions';

  const btnEditar = document.createElement('button');
  btnEditar.className = 'chat-act';
  btnEditar.title = 'Cambiar nombre';
  btnEditar.innerHTML = ICONO_EDITAR;

  const btnBorrar = document.createElement('button');
  btnBorrar.className = 'chat-act';
  btnBorrar.title = 'Eliminar chat';
  btnBorrar.innerHTML = ICONO_BORRAR;

  acciones.appendChild(btnEditar);
  acciones.appendChild(btnBorrar);
  item.appendChild(acciones);

  item.addEventListener('click', () => abrirChat(chatInfo.id));

  btnEditar.addEventListener('click', (e) => {
    e.stopPropagation();
    empezarRenombrar(item, titulo, chatInfo);
  });

  btnBorrar.addEventListener('click', (e) => {
    e.stopPropagation();
    pedirBorrar(item, btnBorrar, chatInfo);
  });

  return item;
}


// ---------- refrescar ----------

async function refrescarChats() {

  const api = chatsApi();

  if (!api || !api.chats_listar) return;

  // No redibujar mientras se está escribiendo un nombre nuevo.
  if (document.querySelector('.chat-rename-input')) return;

  try {

    const r = await api.chats_listar(chatSearch.value.trim());

    if (r && r.ok) {
      chatActivoId = r.activo;
      dibujarChats(r.chats, r.activo);
    }

  } catch (err) {
    console.error('No se pudo cargar la lista de chats:', err);
  }
}


function refrescarChatsSuave() {

  clearTimeout(temporizadorRefresco);

  temporizadorRefresco = setTimeout(refrescarChats, 400);
}


// ---------- pantalla ----------

function limpiarPantallaChat() {

  chat.innerHTML = '';
  chat.appendChild(emptyState);

  input.value = '';
  textoDictado = false;
  autoResize();
}


// ---------- abrir / nuevo ----------

async function abrirChat(id) {

  if (enviando || dictando || dictadoTerminando) return;
  if (id === chatActivoId) return;

  const api = chatsApi();

  if (!api) return;

  try {

    const r = await api.chat_abrir(id);

    if (!r || !r.ok) {
      refrescarChats();
      return;
    }

    limpiarPantallaChat();

    (r.mensajes || []).forEach((m) => {
      addMessage(m.content, m.role === 'assistant' ? 'ai' : 'user');
    });

    chatActivoId = r.id;

    chat.scrollTop = chat.scrollHeight;

    refrescarChats();

    input.focus();

  } catch (err) {
    console.error('No se pudo abrir el chat:', err);
  }
}


async function nuevoChat() {

  if (enviando || dictando || dictadoTerminando) return;

  const api = chatsApi();

  if (!api) return;

  try {

    await api.nuevo_chat();

    chatActivoId = null;

    limpiarPantallaChat();

    refrescarChats();

    input.focus();

  } catch (err) {
    console.error('No se pudo crear el chat nuevo:', err);
  }
}


// ---------- renombrar ----------

function empezarRenombrar(item, tituloEl, chatInfo) {

  const campo = document.createElement('input');
  campo.type = 'text';
  campo.className = 'chat-rename-input';
  campo.value = chatInfo.titulo;
  campo.maxLength = 80;

  item.replaceChild(campo, tituloEl);

  campo.focus();
  campo.select();

  let terminado = false;

  const terminar = async (guardar) => {

    if (terminado) return;
    terminado = true;

    const nuevo = campo.value.trim();

    if (guardar && nuevo && nuevo !== chatInfo.titulo) {

      try {
        await chatsApi().chat_renombrar(chatInfo.id, nuevo);
      } catch (err) {
        console.error('No se pudo renombrar:', err);
      }
    }

    campo.remove();

    refrescarChats();
  };

  campo.addEventListener('click', (e) => e.stopPropagation());

  campo.addEventListener('keydown', (e) => {

    if (e.key === 'Enter') {
      e.preventDefault();
      terminar(true);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      terminar(false);
    }
  });

  campo.addEventListener('blur', () => terminar(true));
}


// ---------- borrar (dos clics para evitar accidentes) ----------

function pedirBorrar(item, boton, chatInfo) {

  if (boton.classList.contains('armado')) {

    clearTimeout(temporizadorBorrar);

    borrarChat(chatInfo.id);

    return;
  }

  boton.classList.add('armado');
  boton.textContent = '¿Eliminar?';
  boton.title = 'Haz clic otra vez para confirmar';
  item.classList.add('confirmando');

  clearTimeout(temporizadorBorrar);

  temporizadorBorrar = setTimeout(() => {

    boton.classList.remove('armado');
    boton.innerHTML = ICONO_BORRAR;
    boton.title = 'Eliminar chat';
    item.classList.remove('confirmando');

  }, 3000);
}


async function borrarChat(id) {

  if (enviando && id === chatActivoId) return;

  try {

    const r = await chatsApi().chat_borrar(id);

    if (r && r.era_activo) {

      chatActivoId = null;

      limpiarPantallaChat();
    }

  } catch (err) {
    console.error('No se pudo borrar el chat:', err);
  }

  refrescarChats();
}


// ---------- eventos ----------

newChatBtn.addEventListener('click', nuevoChat);

chatSearch.addEventListener('input', () => {

  clearTimeout(temporizadorBusqueda);

  temporizadorBusqueda = setTimeout(refrescarChats, 250);
});

function aplicarBarraLateral(abierta) {

  layout.classList.toggle('collapsed', !abierta);

  try {
    localStorage.setItem('oddye_sidebar', abierta ? '1' : '0');
  } catch (err) { /* sin almacenamiento: no pasa nada */ }
}

sidebarToggle.addEventListener('click', () => {
  aplicarBarraLateral(layout.classList.contains('collapsed'));
});

document.addEventListener('keydown', (e) => {

  // Ctrl + Shift + O = chat nuevo (como en otros asistentes)
  if (e.ctrlKey && e.shiftKey && (e.key === 'O' || e.key === 'o')) {
    e.preventDefault();
    nuevoChat();
  }
});

try {

  if (localStorage.getItem('oddye_sidebar') === '0') {
    layout.classList.add('collapsed');
  }

} catch (err) { /* ignorar */ }

window.addEventListener('pywebviewready', refrescarChats);
