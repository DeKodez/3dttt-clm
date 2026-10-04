import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";

const BLUE = 0x4c9dff;
const RED = 0xff5a5a;
const GOLD = 0xffd166;

const HALF = 1.85;
const SIZE = 3.4;
const CELL = SIZE / 3;

const FACE_DEFS = [
  { name: "Top", pos: [0, HALF, 0], rot: [-Math.PI / 2, 0, 0] },
  { name: "Front", pos: [0, 0, HALF], rot: [0, 0, 0] },
  { name: "Left", pos: [-HALF, 0, 0], rot: [0, -Math.PI / 2, 0] },
  { name: "Bottom", pos: [0, -HALF, 0], rot: [Math.PI / 2, 0, 0] },
  { name: "Back", pos: [0, 0, -HALF], rot: [0, Math.PI, 0] },
  { name: "Right", pos: [HALF, 0, 0], rot: [0, Math.PI / 2, 0] },
];

const canvas = document.getElementById("scene");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x05070d);
scene.fog = new THREE.FogExp2(0x05070d, 0.025);

const cube = new THREE.Group();
scene.add(cube);

const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 100);
camera.position.set(5.4, 4.6, 6.6);

const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.autoRotate = false;
controls.enablePan = false;
controls.minDistance = 4;
controls.maxDistance = 12;
controls.minPolarAngle = 0.25;
controls.maxPolarAngle = Math.PI - 0.25;

scene.add(new THREE.AmbientLight(0x8fa3c8, 0.55));
const keyLight = new THREE.DirectionalLight(0xffffff, 1.1);
keyLight.position.set(6, 9, 7);
scene.add(keyLight);
const rimLight = new THREE.DirectionalLight(0x4466ff, 0.65);
rimLight.position.set(-7, -4, -6);
scene.add(rimLight);

const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(
  new THREE.Vector2(window.innerWidth, window.innerHeight),
  0.85,
  0.55,
  0.5
);
composer.addPass(bloom);

const X_ARM = new THREE.BoxGeometry(CELL * 0.56, CELL * 0.08, CELL * 0.08);
const O_GEO = new THREE.TorusGeometry(CELL * 0.3, CELL * 0.065, 12, 40);
const RING_GEO = new THREE.RingGeometry(CELL * 0.3, CELL * 0.4, 40);
const X_MAT = new THREE.MeshStandardMaterial({
  color: 0x9ecbff, emissive: BLUE, emissiveIntensity: 1.5, roughness: 0.35, metalness: 0.15,
});
const O_MAT = new THREE.MeshStandardMaterial({
  color: 0xffb8b8, emissive: RED, emissiveIntensity: 1.5, roughness: 0.35, metalness: 0.15,
});

function cellLocal(row, col) {
  return new THREE.Vector3(-SIZE / 2 + CELL * (col + 0.5), SIZE / 2 - CELL * (row + 0.5), 0);
}

function makeLabel(text) {
  const labelCanvas = document.createElement("canvas");
  labelCanvas.width = 256;
  labelCanvas.height = 64;
  const ctx = labelCanvas.getContext("2d");
  ctx.font = "600 30px ui-monospace, Menlo, monospace";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillStyle = "rgba(168, 196, 236, 0.92)";
  ctx.fillText(text.toUpperCase(), 128, 34);
  const texture = new THREE.CanvasTexture(labelCanvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const sprite = new THREE.Sprite(
    new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false })
  );
  sprite.scale.set(1.5, 0.375, 1);
  return sprite;
}

const faces = [];
const marks = [];

FACE_DEFS.forEach((def, index) => {
  const group = new THREE.Group();
  group.position.set(...def.pos);
  group.rotation.set(...def.rot);
  cube.add(group);

  const panelMat = new THREE.MeshStandardMaterial({
    color: 0x0d1524,
    emissive: 0x000000,
    emissiveIntensity: 0,
    roughness: 0.75,
    metalness: 0.2,
    transparent: true,
    opacity: 0.93,
    side: THREE.DoubleSide,
  });
  group.add(new THREE.Mesh(new THREE.PlaneGeometry(SIZE, SIZE), panelMat));

  const h = SIZE / 2;
  const borderPts = [
    new THREE.Vector3(-h, -h, 0.002),
    new THREE.Vector3(h, -h, 0.002),
    new THREE.Vector3(h, h, 0.002),
    new THREE.Vector3(-h, h, 0.002),
  ];
  const borderMat = new THREE.LineBasicMaterial({ color: 0x3a5a8c });
  group.add(
    new THREE.LineLoop(
      new THREE.BufferGeometry().setFromPoints(borderPts),
      borderMat
    )
  );

  const gridPts = [];
  for (let k = 1; k <= 2; k += 1) {
    const p = -h + k * CELL;
    gridPts.push(new THREE.Vector3(p, -h, 0.003), new THREE.Vector3(p, h, 0.003));
    gridPts.push(new THREE.Vector3(-h, p, 0.003), new THREE.Vector3(h, p, 0.003));
  }
  group.add(
    new THREE.LineSegments(
      new THREE.BufferGeometry().setFromPoints(gridPts),
      new THREE.LineBasicMaterial({ color: 0x233754, transparent: true, opacity: 0.95 })
    )
  );

  const label = makeLabel(def.name);
  label.position.set(0, h + 0.36, 0.01);
  group.add(label);

  faces.push({ group, panelMat, borderMat, label, winLine: null });
  marks.push(
    Array.from({ length: 3 }, () => Array.from({ length: 3 }, () => null))
  );
});

const FACE_PRESENTATION = FACE_DEFS.map((def) => {
  const rotation = new THREE.Euler(...def.rot);
  const normal = new THREE.Vector3(0, 0, 1).applyEuler(rotation).normalize();
  const up = new THREE.Vector3(0, 1, 0).applyEuler(rotation).normalize();
  const right = new THREE.Vector3().crossVectors(up, normal).normalize();
  return { normal, up, right };
});

function buildMark(value) {
  const group = new THREE.Group();
  if (value === "X") {
    const armA = new THREE.Mesh(X_ARM, X_MAT);
    armA.rotation.z = Math.PI / 4;
    const armB = new THREE.Mesh(X_ARM, X_MAT);
    armB.rotation.z = -Math.PI / 4;
    group.add(armA, armB);
  } else {
    group.add(new THREE.Mesh(O_GEO, O_MAT));
  }
  group.userData.value = value;
  return group;
}

function removeMark(faceIndex, row, col) {
  const mark = marks[faceIndex][row][col];
  if (!mark) return;
  faces[faceIndex].group.remove(mark);
  marks[faceIndex][row][col] = null;
}

function clearBoard() {
  clearCloudEffects();
  for (let f = 0; f < 6; f += 1) {
    for (let r = 0; r < 3; r += 1) {
      for (let c = 0; c < 3; c += 1) removeMark(f, r, c);
    }
    const face = faces[f];
    face.panelMat.emissive.setHex(0x000000);
    face.panelMat.emissiveIntensity = 0;
    face.panelMat.opacity = 0.93;
    if (face.winLine) {
      face.group.remove(face.winLine);
      face.winLine.geometry.dispose();
      face.winLine = null;
    }
  }
}

function drawWinLine(faceIndex, cells) {
  const a = cellLocal(cells[0][0], cells[0][1]);
  const b = cellLocal(cells[2][0], cells[2][1]);
  const dir = new THREE.Vector3().subVectors(b, a);
  const mid = new THREE.Vector3().addVectors(a, b).multiplyScalar(0.5);
  const geo = new THREE.CylinderGeometry(CELL * 0.05, CELL * 0.05, dir.length() + CELL * 0.5, 12);
  const mat = new THREE.MeshStandardMaterial({
    color: GOLD, emissive: GOLD, emissiveIntensity: 1.7, transparent: true, opacity: 0.92,
  });
  const cyl = new THREE.Mesh(geo, mat);
  cyl.position.copy(mid);
  cyl.position.z = 0.03;
  cyl.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.clone().normalize());
  faces[faceIndex].group.add(cyl);
  faces[faceIndex].winLine = cyl;
}

function applyState(state) {
  state.faces.forEach((faceState, f) => {
    for (let r = 0; r < 3; r += 1) {
      for (let c = 0; c < 3; c += 1) {
        const value = faceState.cells[r][c];
        const existing = marks[f][r][c];
        if (value === " ") {
          if (existing) removeMark(f, r, c);
        } else if (!existing || existing.userData.value !== value) {
          if (existing) removeMark(f, r, c);
          const mark = buildMark(value);
          mark.position.copy(cellLocal(r, c));
          mark.position.z = 0.05;
          faces[f].group.add(mark);
          marks[f][r][c] = mark;
        }
      }
    }
    const panel = faces[f].panelMat;
    if (faceState.status === "won_x" || faceState.status === "won_o") {
      panel.emissive.setHex(faceState.status === "won_x" ? BLUE : RED);
      panel.emissiveIntensity = 0.22;
      panel.opacity = 0.9;
    } else if (faceState.status === "draw") {
      panel.emissive.setHex(0x8899aa);
      panel.emissiveIntensity = 0.1;
      panel.opacity = 0.9;
    } else {
      panel.emissive.setHex(0x000000);
      panel.emissiveIntensity = 0;
      panel.opacity = 0.93;
    }

    // Gold frame marks the face in play; everything else stays steel blue
    const active = !state.game_over && f === state.active_face;
    faces[f].borderMat.color.setHex(active ? GOLD : 0x3a5a8c);
    if (active && faceState.status === "in_progress") {
      panel.emissive.setHex(GOLD);
      panel.emissiveIntensity = 0.07;
    }
    const wantsLine = Boolean(faceState.winning_cells);
    if (wantsLine && !faces[f].winLine) drawWinLine(f, faceState.winning_cells);
    if (!wantsLine && faces[f].winLine) {
      faces[f].group.remove(faces[f].winLine);
      faces[f].winLine.geometry.dispose();
      faces[f].winLine = null;
    }
  });
  updateHud(state);
}

const scoreX = document.getElementById("score-x");
const scoreO = document.getElementById("score-o");
const turnChip = document.getElementById("turn-chip");
const gameCounter = document.getElementById("game-counter");

function updateHud(state) {
  scoreX.textContent = state.scores.X ?? 0;
  scoreO.textContent = state.scores.O ?? 0;
  if (state.game_over) {
    turnChip.textContent = "game over";
    turnChip.className = "chip over";
  } else {
    const faceName = FACE_DEFS[state.active_face]?.name ?? "";
    turnChip.textContent = `${state.current_player} to move \u00b7 ${faceName}`;
    turnChip.className = `chip ${state.current_player === "X" ? "x" : "o"}`;
  }
}

const pulses = [];
function pulseAt(faceIndex, row, col, color) {
  const ring = new THREE.Mesh(
    RING_GEO,
    new THREE.MeshBasicMaterial({
      color, transparent: true, opacity: 0.9, side: THREE.DoubleSide, depthWrite: false,
    })
  );
  ring.position.copy(cellLocal(row, col));
  ring.position.z = 0.07;
  faces[faceIndex].group.add(ring);
  pulses.push({ ring, t: 0 });
}

function makePuffTexture() {
  const size = 128;
  const textureCanvas = document.createElement("canvas");
  textureCanvas.width = size;
  textureCanvas.height = size;
  const ctx = textureCanvas.getContext("2d");
  const gradient = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  gradient.addColorStop(0, "rgba(255, 255, 255, 1)");
  gradient.addColorStop(0.4, "rgba(255, 255, 255, 0.5)");
  gradient.addColorStop(1, "rgba(255, 255, 255, 0)");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, size, size);
  const texture = new THREE.CanvasTexture(textureCanvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

const PUFF_TEXTURE = makePuffTexture();
const PUFF_COLORS = [0xfff3c4, 0xffd166, 0xffab4a, 0xff8c42, 0xc46b50, 0x94a3b8];
const cloudParticles = [];
const shockwaves = [];

function addPuff(faceIndex, options) {
  const material = new THREE.SpriteMaterial({
    map: PUFF_TEXTURE,
    color: options.color,
    transparent: true,
    opacity: options.opacity,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const sprite = new THREE.Sprite(material);
  sprite.position.set(options.x, options.y, options.z);
  sprite.scale.setScalar(options.size);
  sprite.renderOrder = 6;
  faces[faceIndex].group.add(sprite);
  cloudParticles.push({ sprite, life: 0, ...options });
}

function spawnMushroomCloud(faceIndex) {
  const rand = (min, max) => min + Math.random() * (max - min);
  const pick = () => PUFF_COLORS[Math.floor(Math.random() * PUFF_COLORS.length)];

  addPuff(faceIndex, {
    x: 0, y: -0.2, z: 0.22, vx: 0, vy: 0, gravity: 0,
    size: 0.9, grow: 5.4, opacity: 1, ttl: 0.3, delay: 0, color: 0xfff6d8,
  });

  const ring = new THREE.Mesh(
    RING_GEO,
    new THREE.MeshBasicMaterial({
      color: 0xffcf8f, transparent: true, opacity: 0.9, side: THREE.DoubleSide, depthWrite: false,
    })
  );
  ring.position.set(0, -1.15, 0.16);
  ring.scale.setScalar(0.7);
  ring.renderOrder = 6;
  faces[faceIndex].group.add(ring);
  shockwaves.push({ ring, life: 0, ttl: 0.6 });

  for (let i = 0; i < 12; i += 1) {
    addPuff(faceIndex, {
      x: rand(-0.24, 0.24), y: -1.5, z: 0.16,
      vx: rand(-0.25, 0.25), vy: rand(1.7, 2.4), gravity: 0,
      size: rand(0.28, 0.5), grow: rand(0.9, 1.4), opacity: 0.85,
      ttl: rand(0.6, 1.0), delay: rand(0, 0.16), color: pick(),
    });
  }

  for (let i = 0; i < 20; i += 1) {
    const angle = Math.random() * Math.PI * 2;
    const speed = rand(0.5, 1.6);
    addPuff(faceIndex, {
      x: rand(-0.3, 0.3), y: rand(-0.35, 0.15), z: 0.22,
      vx: Math.cos(angle) * speed, vy: rand(0.25, 0.9) + Math.sin(angle) * speed * 0.35, gravity: 0,
      size: rand(0.45, 0.7), grow: rand(1.8, 2.7), opacity: rand(0.55, 0.8),
      ttl: rand(0.8, 1.3), delay: rand(0.1, 0.38), color: pick(),
    });
  }

  for (let i = 0; i < 18; i += 1) {
    addPuff(faceIndex, {
      x: rand(-0.35, 0.35), y: rand(-0.7, 0), z: 0.26,
      vx: rand(-1.6, 1.6), vy: rand(0.4, 2.0), gravity: -3.6,
      size: rand(0.09, 0.18), grow: 0.06, opacity: 0.95,
      ttl: rand(0.45, 0.85), delay: rand(0, 0.2), color: 0xffe08a,
    });
  }
}

function clearCloudEffects() {
  for (const particle of cloudParticles) {
    particle.sprite.parent?.remove(particle.sprite);
    particle.sprite.material.dispose();
  }
  cloudParticles.length = 0;
  for (const wave of shockwaves) {
    wave.ring.parent?.remove(wave.ring);
    wave.ring.material.dispose();
  }
  shockwaves.length = 0;
}

function updateCloudEffects(dt) {
  for (let i = cloudParticles.length - 1; i >= 0; i -= 1) {
    const particle = cloudParticles[i];
    if (particle.delay > 0) {
      particle.delay -= dt;
      continue;
    }
    particle.life += dt;
    const progress = particle.life / particle.ttl;
    if (progress >= 1) {
      particle.sprite.parent?.remove(particle.sprite);
      particle.sprite.material.dispose();
      cloudParticles.splice(i, 1);
      continue;
    }
    particle.vy += particle.gravity * dt;
    particle.sprite.position.x += particle.vx * dt;
    particle.sprite.position.y += particle.vy * dt;
    const eased = 1 - (1 - progress) * (1 - progress);
    particle.sprite.scale.setScalar(particle.size + particle.grow * eased);
    particle.sprite.material.opacity = particle.opacity * Math.pow(1 - progress, 1.6);
  }

  for (let i = shockwaves.length - 1; i >= 0; i -= 1) {
    const wave = shockwaves[i];
    wave.life += dt;
    const progress = wave.life / wave.ttl;
    if (progress >= 1) {
      wave.ring.parent?.remove(wave.ring);
      wave.ring.material.dispose();
      shockwaves.splice(i, 1);
      continue;
    }
    const scale = 0.7 + progress * 4.6;
    wave.ring.scale.set(scale, scale, 1);
    wave.ring.material.opacity = 0.85 * (1 - progress);
  }
}

let presentedFace = 1;
let faceChangeSeq = 0;
const cameraDir = new THREE.Vector3();
const upTarget = new THREE.Vector3();
const rightTarget = new THREE.Vector3();
const sourceBasis = new THREE.Matrix4();
const targetBasis = new THREE.Matrix4();
const orientation = new THREE.Matrix4();
const targetQuaternion = new THREE.Quaternion();

function presentFace(faceIndex) {
  if (faceIndex === null || faceIndex === undefined) return;
  presentedFace = faceIndex;
}

function presentMove(playedFace, nextFace) {
  faceChangeSeq += 1;
  const seq = faceChangeSeq;
  presentFace(playedFace);
  if (nextFace !== playedFace) {
    setTimeout(() => {
      if (seq === faceChangeSeq) presentFace(nextFace);
    }, swingDelay());
  }
}

function swingDelay() {
  const active = document.querySelector(".speed.active");
  const pace = active ? Number(active.dataset.delay) : 0.8;
  return Math.max(120, pace * 1000 * 0.5);
}

function cubeQuaternionFor(faceIndex, out) {
  const basis = FACE_PRESENTATION[faceIndex];
  cameraDir.copy(camera.position).normalize();
  upTarget.set(0, 1, 0).addScaledVector(cameraDir, -cameraDir.y).normalize();
  rightTarget.crossVectors(upTarget, cameraDir);
  sourceBasis.makeBasis(basis.right, basis.up, basis.normal);
  targetBasis.makeBasis(rightTarget, upTarget, cameraDir);
  orientation.copy(targetBasis).multiply(sourceBasis.transpose());
  return out.setFromRotationMatrix(orientation);
}

function snapPresentation(faceIndex) {
  faceChangeSeq += 1;
  presentFace(faceIndex);
  cube.quaternion.copy(cubeQuaternionFor(presentedFace, targetQuaternion));
}

function updatePresentation(dt) {
  cubeQuaternionFor(presentedFace, targetQuaternion);
  cube.quaternion.slerp(targetQuaternion, 1 - Math.exp(-4.5 * dt));
}

const clock = new THREE.Clock();

function animate() {
  requestAnimationFrame(animate);
  const dt = clock.getDelta();

  for (let i = pulses.length - 1; i >= 0; i -= 1) {
    const pulse = pulses[i];
    pulse.t += dt / 0.75;
    const scale = 1 + pulse.t * 1.4;
    pulse.ring.scale.set(scale, scale, 1);
    pulse.ring.material.opacity = Math.max(0, 0.9 * (1 - pulse.t));
    if (pulse.t >= 1) {
      faces.forEach((face) => face.group.remove(pulse.ring));
      pulse.ring.material.dispose();
      pulses.splice(i, 1);
    }
  }

  updatePresentation(dt);
  updateCloudEffects(dt);
  controls.update();
  composer.render();
}
requestAnimationFrame(animate);

window.addEventListener("resize", () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  composer.setSize(window.innerWidth, window.innerHeight);
});

const banner = document.getElementById("banner");
const bannerTitle = banner.querySelector(".banner-title");
const bannerSub = banner.querySelector(".banner-sub");
let bannerTimer = null;

function showBanner(title, sub, ms = 1800) {
  bannerTitle.textContent = title;
  bannerSub.textContent = sub || "";
  banner.classList.remove("hidden");
  clearTimeout(bannerTimer);
  bannerTimer = setTimeout(() => banner.classList.add("hidden"), ms);
}

const errorBox = document.getElementById("error");
let errorTimer = null;

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
  clearTimeout(errorTimer);
  errorTimer = setTimeout(() => errorBox.classList.add("hidden"), 4500);
}

const connDot = document.getElementById("conn-dot");
const connText = document.getElementById("conn-text");
const startButton = document.getElementById("start");
const agentASelect = document.getElementById("agent-a");
const agentBSelect = document.getElementById("agent-b");
const gamesInput = document.getElementById("games");
const seedInput = document.getElementById("seed");
const statsBody = document.querySelector("#stats-table tbody");
const latencyCanvas = document.getElementById("latency");
const latencyCtx = latencyCanvas.getContext("2d");

const isBroadcast = new URLSearchParams(location.search).get("broadcast") === "1";
if (isBroadcast) document.body.classList.add("broadcast");

let socket = null;
let session = 0;
let running = false;
let autoStarted = false;
let matchAgents = [];
let currentX = null;
let currentO = null;
let gameIndex = 0;
let totalGames = 0;
const liveStats = new Map();
const latencySeries = [];

function newStat(name) {
  return {
    name, games: 0, wins: 0, losses: 0, draws: 0,
    moves: 0, invalid: 0, errors: 0, latencies: [],
  };
}

function percentile(values, fraction) {
  if (!values.length) return 0;
  const ordered = [...values].sort((a, b) => a - b);
  const index = Math.min(ordered.length - 1, Math.max(0, Math.round(fraction * (ordered.length - 1))));
  return ordered[index];
}

function renderStats() {
  statsBody.innerHTML = "";
  for (const name of matchAgents) {
    const stat = liveStats.get(name);
    if (!stat) continue;
    const row = document.createElement("tr");
    row.className = name === currentX ? "agent-a" : "agent-b";
    const cells = [
      name,
      `${stat.wins}–${stat.losses}–${stat.draws}`,
      stat.games ? `${Math.round((stat.wins / stat.games) * 100)}%` : "—",
      `${Math.round(percentile(stat.latencies, 0.5))}`,
      `${Math.round(percentile(stat.latencies, 0.95))}`,
      `${stat.invalid}`,
      `${stat.errors}`,
    ];
    cells.forEach((text, i) => {
      const td = document.createElement("td");
      if (i === 0) td.className = "name";
      td.textContent = text;
      row.appendChild(td);
    });
    statsBody.appendChild(row);
  }
}

function renderLatencyChart() {
  const width = latencyCanvas.width;
  const height = latencyCanvas.height;
  latencyCtx.clearRect(0, 0, width, height);
  const series = latencySeries.slice(-90);
  const max = Math.max(500, ...series.map((entry) => entry.ms));
  const barWidth = Math.max(2, Math.floor(width / Math.max(series.length, 1)) - 1);
  series.forEach((entry, i) => {
    const h = Math.max(2, (entry.ms / max) * (height - 14));
    latencyCtx.fillStyle = entry.agent === currentX ? "rgba(76, 157, 255, 0.85)" : "rgba(255, 90, 90, 0.85)";
    latencyCtx.fillRect(i * (barWidth + 1), height - h, barWidth, h);
  });
  latencyCtx.fillStyle = "rgba(124, 141, 176, 0.9)";
  latencyCtx.font = "9px ui-monospace, monospace";
  latencyCtx.fillText(`${Math.round(max)} ms`, 4, 10);
}

function send(message) {
  if (socket && socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify(message));
}

function startMatch() {
  if (running) return;
  session += 1;
  running = true;
  startButton.disabled = true;
  const delay = Number(document.querySelector(".speed.active").dataset.delay);
  send({
    type: "start",
    session,
    agent_a: agentASelect.value,
    agent_b: agentBSelect.value,
    games: Number(gamesInput.value) || 1,
    seed: Number(seedInput.value) || 0,
    min_move_delay: delay,
  });
}

function handleEvent(message) {
  switch (message.type) {
    case "catalog": {
      const options = message.agents || [];
      for (const select of [agentASelect, agentBSelect]) {
        select.innerHTML = "";
        for (const name of options) {
          const option = document.createElement("option");
          option.value = name;
          option.textContent = name;
          select.appendChild(option);
        }
      }
      if (options.includes("jev")) agentASelect.value = "jev";
      if (options.includes("tactical")) agentBSelect.value = "tactical";
      if (isBroadcast && !autoStarted) {
        autoStarted = true;
        startMatch();
      }
      break;
    }
    case "match_start": {
      matchAgents = message.agents;
      totalGames = message.games;
      gameIndex = 0;
      liveStats.clear();
      matchAgents.forEach((name) => liveStats.set(name, newStat(name)));
      latencySeries.length = 0;
      currentX = null;
      currentO = null;
      document.getElementById("matchup").textContent = `${matchAgents[0]} vs ${matchAgents[1]}`;
      gameCounter.textContent = `${totalGames} game${totalGames === 1 ? "" : "s"}`;
      showBanner("MATCH UP", `${matchAgents[0]} vs ${matchAgents[1]} — ${totalGames} games`, 1600);
      renderStats();
      renderLatencyChart();
      break;
    }
    case "game_start": {
      gameIndex += 1;
      currentX = message.x_agent;
      currentO = message.o_agent;
      gameCounter.textContent = `game ${gameIndex} / ${totalGames}`;
      clearBoard();
      applyState(message.state);
      snapPresentation(message.state.active_face);
      showBanner(`GAME ${gameIndex}`, `${currentX} is X · ${currentO} is O`, 1400);
      renderStats();
      break;
    }
    case "move": {
      applyState(message.state);
      const [faceIndex, row, col] = message.move;
      const isNuke = row === -1;
      if (isNuke) {
        spawnMushroomCloud(faceIndex);
        pulseAt(faceIndex, 1, 1, GOLD);
        showBanner("NUKE", `${FACE_DEFS[faceIndex].name} face wiped`, 1600);
        presentMove(faceIndex, faceIndex);
      } else {
        pulseAt(faceIndex, row, col, message.player === currentX ? BLUE : RED);
        presentMove(faceIndex, message.state.active_face ?? faceIndex);
      }
      const stat = liveStats.get(message.player);
      if (stat) {
        stat.moves += 1;
        stat.latencies.push(message.latency_ms);
        if (message.invalid) stat.invalid += 1;
        if (message.error) stat.errors += 1;
      }
      latencySeries.push({ agent: message.player, ms: message.latency_ms });
      renderStats();
      renderLatencyChart();
      break;
    }
    case "game_end": {
      applyState(message.state);
      for (const name of matchAgents) {
        const stat = liveStats.get(name);
        if (!stat) continue;
        stat.games += 1;
        if (!message.winner) stat.draws += 1;
        else if (name === (message.winner === "X" ? currentX : currentO)) stat.wins += 1;
        else stat.losses += 1;
      }
      const winnerName = message.winner
        ? message.winner === "X" ? currentX : currentO
        : null;
      showBanner(
        winnerName ? `${winnerName.toUpperCase()} WINS` : "DRAW",
        message.result_label,
        2200
      );
      renderStats();
      break;
    }
    case "match_end": {
      running = false;
      startButton.disabled = false;
      const stats = message.result.stats || {};
      for (const [name, summary] of Object.entries(stats)) {
        const stat = liveStats.get(name);
        if (!stat) continue;
        stat.games = summary.games;
        stat.wins = summary.wins;
        stat.losses = summary.losses;
        stat.draws = summary.draws;
        stat.moves = summary.moves;
        stat.invalid = summary.invalid_moves;
        stat.errors = summary.errors;
        stat.latencies = stat.latencies.length ? stat.latencies : [];
      }
      renderStats();
      const a = stats[matchAgents[0]];
      const b = stats[matchAgents[1]];
      if (a && b) {
        const winner = a.wins === b.wins ? "SERIES DRAW" : `${a.wins > b.wins ? matchAgents[0] : matchAgents[1]} WINS THE SERIES`;
        showBanner(winner, `${matchAgents[0]} ${a.wins} – ${b.wins} ${matchAgents[1]}`, 4200);
      }
      break;
    }
    case "error":
      showError(message.message);
      if (running) {
        running = false;
        startButton.disabled = false;
      }
      break;
    default:
      break;
  }
}

document.querySelectorAll(".speed").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".speed").forEach((b) => b.classList.remove("active"));
    button.classList.add("active");
  });
});

startButton.addEventListener("click", startMatch);

function connect() {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  socket = new WebSocket(`${protocol}//${location.host}/ws`);
  socket.addEventListener("open", () => {
    connDot.className = "dot on";
    connText.textContent = "connected";
    send({ type: "catalog" });
  });
  socket.addEventListener("close", () => {
    connDot.className = "dot off";
    connText.textContent = "reconnecting…";
    if (running) {
      running = false;
      startButton.disabled = false;
    }
    setTimeout(connect, 2000);
  });
  socket.addEventListener("message", (event) => {
    try {
      handleEvent(JSON.parse(event.data));
    } catch (err) {
      showError(String(err));
    }
  });
}

connect();
