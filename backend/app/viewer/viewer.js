// Kamra 3D tour viewer — projects each room's 360° panorama onto a room-shaped shell
// so the user can look around, walk inside, hop between rooms and see a dollhouse view.
import * as THREE from './three.module.js';

const $ = (id) => document.getElementById(id);
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const params = new URLSearchParams(location.search);
const tourId = params.get('tour') || '';
const previewToken = params.get('t');
const EYE = 1.5;
const MARGIN = 0.35;
const isTouch = matchMedia('(pointer: coarse)').matches || 'ontouchstart' in window;
const lowMemory = (navigator.deviceMemory && navigator.deviceMemory <= 2) || Math.min(screen.width, screen.height) < 400;
const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
if (isTouch) document.body.classList.add('touch');

function post(msg) {
  try { window.ReactNativeWebView?.postMessage(JSON.stringify(msg)); } catch { /* not in RN */ }
  try { if (window.parent !== window) window.parent.postMessage({ source: 'kamra-viewer', ...msg }, '*'); } catch { /* cross-origin */ }
}

// ------------------------------------------------------------------ renderer & scene
const stage = $('stage');
let renderer;
try {
  renderer = new THREE.WebGLRenderer({ antialias: !lowMemory, powerPreference: 'high-performance' });
} catch (e) {
  fail('Your device does not support 3D graphics (WebGL).');
  throw e;
}
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, lowMemory ? 1.5 : 2));
renderer.outputColorSpace = THREE.LinearSRGBColorSpace; // pano bytes pass through unchanged
stage.appendChild(renderer.domElement);
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0b1220);
const camera = new THREE.PerspectiveCamera(75, 1, 0.05, 300);
camera.rotation.order = 'YXZ';
const maxAniso = renderer.capabilities.getMaxAnisotropy();

const vert = /* glsl */`
  varying vec3 vWorld;
  void main() {
    vec4 w = modelMatrix * vec4(position, 1.0);
    vWorld = w.xyz;
    gl_Position = projectionMatrix * viewMatrix * w;
  }`;
const frag = /* glsl */`
  precision highp float;
  uniform sampler2D map;
  uniform vec3 center;
  uniform float yaw;
  uniform float shade;
  varying vec3 vWorld;
  const float PI = 3.141592653589793;
  void main() {
    vec3 d = normalize(vWorld - center);
    float theta = atan(d.x, -d.z) + yaw;
    float phi = acos(clamp(d.y, -1.0, 1.0));
    vec2 uv = vec2(fract(theta / (2.0 * PI) + 0.5), 1.0 - phi / PI);
    gl_FragColor = vec4(texture2D(map, uv).rgb * shade, 1.0);
  }`;

// ------------------------------------------------------------------ state
const state = {
  manifest: null,
  rooms: [],          // {data, group, floor, material, bounds, center, rings}
  current: 0,
  mode: 'walk',       // walk | dollhouse
  yaw: 0, pitch: 0, fov: 75,
  target: null,       // walk-to target (Vector3)
  orbit: { az: Math.PI / 4, el: 0.9, dist: 12, center: new THREE.Vector3() },
  keys: new Set(),
  joy: { x: 0, y: 0 },
};

// ------------------------------------------------------------------ loading
async function load() {
  $('error').hidden = true;
  $('loading').hidden = false;
  if (!UUID.test(tourId)) return fail('This tour link is invalid.');
  let manifest;
  try {
    const q = previewToken ? `?t=${encodeURIComponent(previewToken)}` : '';
    const res = await fetch(`/api/v1/tours/${tourId}/manifest${q}`, { credentials: 'omit' });
    if (res.status === 404) return fail('This tour is not published or no longer exists.');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    manifest = await res.json();
  } catch (e) {
    return fail('Could not reach the server. Check your connection and try again.');
  }
  if (!manifest.rooms?.length) return fail('This tour has no rooms yet.');
  state.manifest = manifest;
  $('title').textContent = manifest.title || '3D Tour';
  document.title = `${manifest.title || '3D Tour'} · Kamra`;
  buildScene(manifest);
  buildRoomBar();
  const loader = new THREE.TextureLoader();
  let done = 0;
  const total = manifest.rooms.length;
  const setProgress = () => { $('loading-bar').style.width = `${Math.round((done / total) * 100)}%`; };
  setProgress();
  // Progressive: low-res first for every room (fast first paint), then upgrade to 4K.
  await Promise.all(state.rooms.map((room) => new Promise((resolve) => {
    loader.load(room.data.pano_small || room.data.pano, (tex) => {
      applyTexture(room, tex); done++; setProgress(); resolve();
    }, undefined, () => { done++; setProgress(); resolve(); });
  })));
  $('loading').hidden = true;
  enterRoom(0, true);
  post({ type: 'ready', rooms: total, width: innerWidth, height: innerHeight });
  try {
    if (!localStorage.getItem('kamra.viewer.help')) showHelp(true);
  } catch { showHelp(true); }
  if (!lowMemory) {
    for (const room of state.rooms) {
      if (room.data.pano && room.data.pano !== room.data.pano_small) {
        loader.load(room.data.pano, (tex) => applyTexture(room, tex));
      }
    }
  }
}

function applyTexture(room, tex) {
  tex.generateMipmaps = false;            // avoids a seam at the 360° wrap
  tex.minFilter = THREE.LinearFilter;
  tex.magFilter = THREE.LinearFilter;
  tex.wrapS = THREE.RepeatWrapping;
  tex.anisotropy = maxAniso;
  const old = room.material.uniforms.map.value;
  room.material.uniforms.map.value = tex;
  room.material.uniforms.shade.value = 1;
  if (old && old !== tex) old.dispose();
}

function fail(msg) {
  $('loading').hidden = true;
  $('error-text').textContent = msg;
  $('error').hidden = false;
  post({ type: 'error', message: msg });
}

// ------------------------------------------------------------------ scene construction
function plane(w, h, material) {
  return new THREE.Mesh(new THREE.PlaneGeometry(w, h), material);
}

function buildScene(manifest) {
  const placeholder = new THREE.DataTexture(new Uint8Array([60, 70, 90, 255]), 1, 1);
  placeholder.needsUpdate = true;
  const min = new THREE.Vector3(Infinity, 0, Infinity);
  const max = new THREE.Vector3(-Infinity, 0, -Infinity);
  manifest.rooms.forEach((data, i) => {
    const W = data.width, L = data.length, H = data.height;
    const [ox, oz] = data.origin;
    const center = new THREE.Vector3(ox, data.camera_height || EYE, oz);
    const material = new THREE.ShaderMaterial({
      uniforms: {
        map: { value: placeholder },
        center: { value: center },
        yaw: { value: THREE.MathUtils.degToRad(data.yaw_offset || 0) },
        shade: { value: 0.6 },
      },
      vertexShader: vert, fragmentShader: frag, side: THREE.FrontSide,
    });
    const group = new THREE.Group();
    // All faces point INTO the room: visible from inside; from outside the near walls
    // and the ceiling are back-face culled automatically → free "dollhouse" cut-away.
    const floor = plane(W, L, material); floor.rotation.x = -Math.PI / 2; floor.position.set(ox, 0, oz);
    const ceil = plane(W, L, material); ceil.rotation.x = Math.PI / 2; ceil.position.set(ox, H, oz);
    const north = plane(W, H, material); north.position.set(ox, H / 2, oz - L / 2);
    const south = plane(W, H, material); south.rotation.y = Math.PI; south.position.set(ox, H / 2, oz + L / 2);
    const west = plane(L, H, material); west.rotation.y = Math.PI / 2; west.position.set(ox - W / 2, H / 2, oz);
    const east = plane(L, H, material); east.rotation.y = -Math.PI / 2; east.position.set(ox + W / 2, H / 2, oz);
    floor.userData = { room: i, floor: true };
    group.add(floor, ceil, north, south, west, east);
    scene.add(group);
    const bounds = { minX: ox - W / 2 + MARGIN, maxX: ox + W / 2 - MARGIN, minZ: oz - L / 2 + MARGIN, maxZ: oz + L / 2 - MARGIN };
    state.rooms.push({ data, group, floor, material, bounds, center, rings: [] });
    min.x = Math.min(min.x, ox - W / 2); min.z = Math.min(min.z, oz - L / 2);
    max.x = Math.max(max.x, ox + W / 2); max.z = Math.max(max.z, oz + L / 2);
  });
  // Door hotspots between linked rooms.
  const ringGeo = new THREE.RingGeometry(0.22, 0.32, 40);
  const ringMat = new THREE.MeshBasicMaterial({ color: 0x2dd4bf, transparent: true, opacity: 0.9, side: THREE.DoubleSide, depthTest: false });
  const byId = Object.fromEntries(state.rooms.map((r, i) => [r.data.id, i]));
  for (const link of manifest.links || []) {
    const a = byId[link.from], b = byId[link.to];
    if (a === undefined || b === undefined) continue;
    for (const [from, to] of [[a, b], [b, a]]) {
      const r = state.rooms[from], t = state.rooms[to];
      const dir = Math.sign(t.center.x - r.center.x) || 1;
      const ring = new THREE.Mesh(ringGeo, ringMat);
      ring.rotation.x = -Math.PI / 2;
      ring.position.set(r.center.x + dir * (r.data.width / 2 - 0.7), 0.02, r.center.z);
      ring.renderOrder = 10;
      ring.userData = { goto: to };
      r.group.add(ring);
      r.rings.push(ring);
    }
  }
  state.orbit.center.set((min.x + max.x) / 2, 0.8, (min.z + max.z) / 2);
  state.orbit.dist = Math.max(8, Math.max(max.x - min.x, max.z - min.z) * 1.25);
}

function buildRoomBar() {
  const bar = $('rooms');
  bar.textContent = '';
  state.rooms.forEach((r, i) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.setAttribute('role', 'tab');
    b.textContent = r.data.name;
    b.addEventListener('click', () => { setMode('walk'); enterRoom(i); });
    bar.appendChild(b);
  });
  if (state.rooms.length < 2) $('topbar').classList.add('single');
}

function updateRoomBar() {
  [...$('rooms').children].forEach((b, i) => b.setAttribute('aria-selected', String(i === state.current && state.mode === 'walk')));
}

// ------------------------------------------------------------------ navigation
const fadeEl = Object.assign(document.createElement('div'), { className: 'fade' });
document.body.appendChild(fadeEl);

function enterRoom(i, instant = false) {
  const go = () => {
    state.current = i;
    const r = state.rooms[i];
    camera.position.set(r.center.x, EYE, r.center.z);
    state.target = null;
    state.yaw = 0; state.pitch = 0;
    updateRoomBar();
    post({ type: 'room', index: i, name: r.data.name });
  };
  if (instant || reduceMotion) return go();
  fadeEl.classList.add('on');
  setTimeout(() => { go(); fadeEl.classList.remove('on'); }, 250);
}

function setMode(mode) {
  if (state.mode === mode) return;
  state.mode = mode;
  document.body.classList.toggle('dollhouse', mode === 'dollhouse');
  $('btn-mode').setAttribute('aria-pressed', String(mode === 'dollhouse'));
  $('btn-mode').querySelector('.label').textContent = mode === 'dollhouse' ? 'Walk' : 'Dollhouse';
  for (const r of state.rooms) r.rings.forEach((ring) => { ring.visible = mode === 'walk'; });
  if (mode === 'walk') enterRoom(state.current);
  updateRoomBar();
}

function clampToRoom(p) {
  const b = state.rooms[state.current].bounds;
  p.x = Math.min(b.maxX, Math.max(b.minX, p.x));
  p.z = Math.min(b.maxZ, Math.max(b.minZ, p.z));
  return p;
}

// ------------------------------------------------------------------ input
const raycaster = new THREE.Raycaster();
const pointers = new Map();
let drag = null;
let pinch = null;

function ndc(e) {
  const rect = renderer.domElement.getBoundingClientRect();
  return new THREE.Vector2(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1);
}

function onTap(e) {
  raycaster.setFromCamera(ndc(e), camera);
  if (state.mode === 'walk') {
    const r = state.rooms[state.current];
    const hit = raycaster.intersectObjects([...r.rings, r.floor], false)[0];
    if (!hit) return;
    if (hit.object.userData.goto !== undefined) return enterRoom(hit.object.userData.goto);
    state.target = clampToRoom(new THREE.Vector3(hit.point.x, EYE, hit.point.z));
  } else {
    const hit = raycaster.intersectObjects(state.rooms.map((r) => r.floor), false)[0];
    if (!hit) return;
    state.current = hit.object.userData.room;
    setMode('walk');
  }
}

stage.addEventListener('pointerdown', (e) => {
  stage.setPointerCapture(e.pointerId);
  pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
  if (pointers.size === 1) {
    drag = { x: e.clientX, y: e.clientY, sx: e.clientX, sy: e.clientY, t: performance.now() };
    stage.classList.add('dragging');
  } else if (pointers.size === 2) {
    const [a, b] = [...pointers.values()];
    pinch = { d: Math.hypot(a.x - b.x, a.y - b.y), fov: state.fov, dist: state.orbit.dist };
    drag = null;
  }
});
stage.addEventListener('pointermove', (e) => {
  if (!pointers.has(e.pointerId)) return;
  pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
  if (pinch && pointers.size === 2) {
    const [a, b] = [...pointers.values()];
    const k = pinch.d / Math.max(1, Math.hypot(a.x - b.x, a.y - b.y));
    if (state.mode === 'walk') state.fov = THREE.MathUtils.clamp(pinch.fov * k, 35, 95);
    else state.orbit.dist = THREE.MathUtils.clamp(pinch.dist * k, 3, 60);
    return;
  }
  if (!drag) return;
  const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
  drag.x = e.clientX; drag.y = e.clientY;
  if (state.mode === 'walk') {
    const k = (state.fov / 75) * 0.0045;
    // "Grab the world": dragging right pans the view left, dragging down looks up.
    state.yaw -= dx * k;
    state.pitch = THREE.MathUtils.clamp(state.pitch + dy * k, -1.45, 1.45);
  } else {
    state.orbit.az -= dx * 0.006;
    state.orbit.el = THREE.MathUtils.clamp(state.orbit.el + dy * 0.004, 0.15, 1.45);
  }
});
const end = (e) => {
  if (drag && pointers.size === 1) {
    const moved = Math.hypot(e.clientX - drag.sx, e.clientY - drag.sy);
    if (moved < 8 && performance.now() - drag.t < 450) onTap(e);
  }
  pointers.delete(e.pointerId);
  if (pointers.size < 2) pinch = null;
  if (pointers.size === 0) { drag = null; stage.classList.remove('dragging'); }
};
stage.addEventListener('pointerup', end);
stage.addEventListener('pointercancel', end);
stage.addEventListener('wheel', (e) => {
  e.preventDefault();
  if (state.mode === 'walk') state.fov = THREE.MathUtils.clamp(state.fov + e.deltaY * 0.03, 35, 95);
  else state.orbit.dist = THREE.MathUtils.clamp(state.orbit.dist * (1 + e.deltaY * 0.001), 3, 60);
}, { passive: false });

window.addEventListener('keydown', (e) => {
  if (e.target instanceof HTMLButtonElement && (e.key === ' ' || e.key === 'Enter')) return;
  const k = e.key.toLowerCase();
  if (['w', 'a', 's', 'd', 'arrowup', 'arrowdown', 'arrowleft', 'arrowright', 'q', 'e'].includes(k)) { state.keys.add(k); e.preventDefault(); }
  if (k === 'escape' && !$('help').hidden) showHelp(false);
});
window.addEventListener('keyup', (e) => state.keys.delete(e.key.toLowerCase()));
window.addEventListener('blur', () => state.keys.clear());

// Joystick (touch)
const joy = $('joystick'), knob = joy.querySelector('.knob');
let joyId = null;
joy.addEventListener('pointerdown', (e) => { joyId = e.pointerId; joy.setPointerCapture(e.pointerId); moveJoy(e); e.stopPropagation(); });
joy.addEventListener('pointermove', (e) => { if (e.pointerId === joyId) moveJoy(e); });
const endJoy = (e) => { if (e.pointerId !== joyId) return; joyId = null; state.joy = { x: 0, y: 0 }; knob.style.transform = ''; };
joy.addEventListener('pointerup', endJoy);
joy.addEventListener('pointercancel', endJoy);
function moveJoy(e) {
  const r = joy.getBoundingClientRect();
  let x = (e.clientX - (r.left + r.width / 2)) / (r.width / 2);
  let y = (e.clientY - (r.top + r.height / 2)) / (r.height / 2);
  const m = Math.hypot(x, y);
  if (m > 1) { x /= m; y /= m; }
  state.joy = { x, y };
  knob.style.transform = `translate(${x * 32}px, ${y * 32}px)`;
}

// Buttons
$('btn-mode').addEventListener('click', () => setMode(state.mode === 'walk' ? 'dollhouse' : 'walk'));
$('btn-help').addEventListener('click', () => showHelp(true));
$('help-close').addEventListener('click', () => showHelp(false));
$('error-retry').addEventListener('click', () => load());
$('btn-full').addEventListener('click', async () => {
  try {
    if (document.fullscreenElement) await document.exitFullscreen();
    else await document.documentElement.requestFullscreen();
  } catch { /* iOS Safari: not supported for documents */ }
});
function showHelp(on) {
  $('help').hidden = !on;
  if (on) $('help-close').focus();
  else { try { localStorage.setItem('kamra.viewer.help', '1'); } catch { /* storage blocked */ } stage.focus(); }
}

// ------------------------------------------------------------------ loop
function resize() {
  const w = window.innerWidth, h = window.innerHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
window.addEventListener('resize', resize);
resize();

const clock = new THREE.Clock();
const fwd = new THREE.Vector3(), right = new THREE.Vector3();
function tick() {
  const dt = Math.min(clock.getDelta(), 0.05);
  if (state.manifest) {
    if (state.mode === 'walk') {
      // keyboard / joystick movement relative to view direction
      let mx = state.joy.x, mz = -state.joy.y;
      if (state.keys.has('w') || state.keys.has('arrowup')) mz += 1;
      if (state.keys.has('s') || state.keys.has('arrowdown')) mz -= 1;
      if (state.keys.has('d')) mx += 1;
      if (state.keys.has('a')) mx -= 1;
      if (state.keys.has('arrowleft') || state.keys.has('q')) state.yaw -= 1.6 * dt;
      if (state.keys.has('arrowright') || state.keys.has('e')) state.yaw += 1.6 * dt;
      if (mx || mz) {
        state.target = null;
        fwd.set(Math.sin(state.yaw), 0, -Math.cos(state.yaw));
        right.set(Math.cos(state.yaw), 0, Math.sin(state.yaw));
        const speed = 1.6 * dt;
        camera.position.addScaledVector(fwd, mz * speed).addScaledVector(right, mx * speed);
        clampToRoom(camera.position);
      } else if (state.target) {
        const k = reduceMotion ? 1 : 1 - Math.pow(0.002, dt);
        camera.position.lerp(state.target, k);
        if (camera.position.distanceTo(state.target) < 0.01) state.target = null;
      }
      camera.position.y = EYE;
      camera.rotation.set(state.pitch, -state.yaw, 0);
      camera.fov += (state.fov - camera.fov) * 0.25;
    } else {
      const o = state.orbit;
      camera.position.set(
        o.center.x + o.dist * Math.cos(o.el) * Math.sin(o.az),
        o.center.y + o.dist * Math.sin(o.el),
        o.center.z + o.dist * Math.cos(o.el) * Math.cos(o.az),
      );
      camera.lookAt(o.center);
      camera.fov += (55 - camera.fov) * 0.2;
    }
    camera.updateProjectionMatrix();
    const pulse = 0.75 + 0.25 * Math.sin(performance.now() / 300);
    for (const r of state.rooms) for (const ring of r.rings) ring.material.opacity = pulse;
  }
  renderer.render(scene, camera);
  requestAnimationFrame(tick);
}
requestAnimationFrame(tick);

// Debug/automation hook (read-only state snapshot) used by end-to-end tests.
window.__kamraViewer = {
  get state() { return { mode: state.mode, current: state.current, rooms: state.rooms.length, pos: camera.position.toArray(), yaw: state.yaw, pitch: state.pitch }; },
  enterRoom: (i) => enterRoom(i, true),
  setMode,
  tapNdc: (x, y) => { const rect = renderer.domElement.getBoundingClientRect(); onTap({ clientX: rect.left + (x + 1) / 2 * rect.width, clientY: rect.top + (1 - y) / 2 * rect.height }); },
};

load();
