console.log("play.js loaded");

// --- grab elements + contexts
const canvas        = document.getElementById("gameCanvas");
const ctx           = canvas.getContext("2d");
const miniMapCanvas = document.getElementById("miniMapCanvas");
const miniCtx       = miniMapCanvas.getContext("2d");
const chatLog       = document.getElementById("chat-log");

// --- resize logic
function resizeCanvas() {
  canvas.width  = window.innerWidth;
  canvas.height = window.innerHeight;
  miniMapCanvas.width  = 200;
  miniMapCanvas.height = 200;
}
window.addEventListener("resize", resizeCanvas);
resizeCanvas();

// --- game constants + state
const tileSize = 50,
      gridCols = 500,
      gridRows = 500,
      gridWidth  = tileSize * gridCols,
      gridHeight = tileSize * gridRows;

let playerX = gridWidth/2,
    playerY = gridHeight/2;
let cameraX = 0,
    cameraY = 0;
let keys = {},
    playerSpeed = 3;
let avatarImg = null;
let tileStates = {1:{},2:{},3:{}};
let otherPlayers = {};
let playerBoardLevel = 1;
let gameStarted = false;
const avatarCache    = {};
const activeRedTiles = {1: new Set(), 2: new Set(), 3: new Set()};

// --- input handling
document.addEventListener("keydown", e => keys[e.key] = true);
document.addEventListener("keyup",   e => keys[e.key] = false);

// --- load own avatar
if (window.PLAYER_AVATAR) {
  avatarImg = new Image();
  avatarImg.src = `/images/${window.PLAYER_AVATAR}`;
  avatarImg.onerror = () => avatarImg.src = `/images/user.webp`;
}

// --- Socket.IO setup
const socket = io('/game', { transports: ['websocket'] });

socket.on("connect",    () => console.log("Socket connected:", socket.id));
socket.on("disconnect", () => console.log("Socket disconnected"));
socket.on("eliminated", data => {
  alert("You've lost!");
  window.location.href = data.redirect;
});
socket.on("victory", data => {
  alert("🎉 Congratulations, you won!");
  window.location.href = data.redirect;
});

socket.on("countdown", data => {
  const cd = document.getElementById("countdown");
  if (data.time > 0) {
    cd.textContent = `Game starts in ${data.time}s…`;
    cd.style.display = "block";
  } else {
    cd.style.display = "none";
  }
});

// ─── INITIAL TILES ──────────────────────────────────────────────────────────
socket.on("tile-init", data => {
  tileStates = {1:{},2:{},3:{}};
  for (let b = 1; b <= 3; b++) {
    for (const key in data.tileStates[b]||{}) {
      const st = data.tileStates[b][key];
      tileStates[b][key] = st;
      if (st === 1) activeRedTiles[b].add(key);
    }
  }
});

// ─── PER-TILE UPDATES ───────────────────────────────────────────────────────
socket.on("tile-update", msg => {
  const { key, state, board } = msg;
  if (state === 0) {
    delete tileStates[board][key];
    activeRedTiles[board].delete(key);
  } else {
    tileStates[board][key] = state;
    if (state === 1) activeRedTiles[board].add(key);
    else activeRedTiles[board].delete(key);
  }
});

// ─── PLAYER LIST ───────────────────────────────────────────────────────────
socket.on("players", msg => {
  otherPlayers = {};
  for (const id in msg.players) {
    const d = msg.players[id];

    if (id === socket.id) {
      // only update board‐level for ourselves
      if (playerX === gridWidth/2) {
        playerX = d.x;  // Update only if the position has changed
      }

      if (playerY === gridHeight/2) {
        playerY = d.y;  // Update only if the position has changed
      }
      playerBoardLevel = d.board_level;
      continue;
    }

    if (!avatarCache[d.avatar]) {
      const img = new Image();
      img.src = `/images/${d.avatar}`;
      img.onerror = () => img.src = `/images/user.webp`;
      avatarCache[d.avatar] = img;
    }
    const prev = otherPlayers[id] || { x: d.x, y: d.y };
    otherPlayers[id] = {
      ...d,
      avatarImg: avatarCache[d.avatar],
      x: prev.x, y: prev.y,
      targetX: d.x, targetY: d.y
    };
  }
});

socket.on("game_start", () => {
  if (!gameStarted) {
     if (!gameStarted) {
      const cd = document.getElementById("countdown");
      cd.style.display = "none";
      gameStarted = true;
      gameLoop();
    }
  }
});

socket.on("chat", msg => addChatMessage(msg.text));

// ─── MOVE + EMIT ──────────────────────────────────────────────────────────
let lastEmit = 0;
function update() {
  let dx = 0, dy = 0;
  if (keys.ArrowUp    || keys.w) dy -= playerSpeed;
  if (keys.ArrowDown  || keys.s) dy += playerSpeed;
  if (keys.ArrowLeft  || keys.a) dx -= playerSpeed;
  if (keys.ArrowRight || keys.d) dx += playerSpeed;

  playerX = Math.max(0, Math.min(playerX + dx, gridWidth));
  playerY = Math.max(0, Math.min(playerY + dy, gridHeight));

  cameraX = Math.max(0, Math.min(playerX + tileSize/2 - canvas.width/2,
                                  gridWidth  - canvas.width));
  cameraY = Math.max(0, Math.min(playerY + tileSize/2 - canvas.height/2,
                                  gridHeight - canvas.height));

  const now = Date.now();
  if (now - lastEmit > 100) {
    socket.emit("move", { x: playerX, y: playerY });
    lastEmit = now;
  }

  // smooth other players
  for (const id in otherPlayers) {
    const p = otherPlayers[id], s = 0.1;
    p.x += (p.targetX - p.x) * s;
    p.y += (p.targetY - p.y) * s;
  }
}

// ─── DRAW LOOP ─────────────────────────────────────────────────────────────
function draw() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.save();
    ctx.translate(-cameraX, -cameraY);

    const B = playerBoardLevel;
    const startCol = Math.floor(cameraX / tileSize),
          endCol   = Math.ceil((cameraX + canvas.width)  / tileSize);
    const startRow = Math.floor(cameraY / tileSize),
          endRow   = Math.ceil((cameraY + canvas.height) / tileSize);

    for (let r = startRow; r < endRow; r++) {
      for (let c = startCol; c < endCol; c++) {
        const k = `${c},${r}`,
              s = tileStates[B][k] || 0,
              x = c * tileSize,
              y = r * tileSize;
        // choose fill
        ctx.fillStyle = (
          s === 1 ? "#F00" :
          s === 2 ? "#000" :
          (B === 1 ? "#fff4dd" : B === 2 ? "#FFF" : "#e2f2ff")
        );
        ctx.fillRect(x, y, tileSize, tileSize);
        ctx.strokeStyle = "#CCC";
        ctx.strokeRect(x, y, tileSize, tileSize);
      }
    }

    drawPlayer(playerX, playerY, window.PLAYER_USERNAME, avatarImg);
    for (const id in otherPlayers) {
      const p = otherPlayers[id];
      if(p.board_level === playerBoardLevel)
      {
      drawPlayer(p.x, p.y, p.username, p.avatarImg);
      }
    }
  ctx.restore();

  // minimap
  const mapW = miniMapCanvas.width,
        mapH = miniMapCanvas.height,
        sx = mapW / gridCols,
        sy = mapH / gridRows;
  miniCtx.clearRect(0, 0, mapW, mapH);
  miniCtx.fillStyle = "#FFF";
  miniCtx.fillRect(0, 0, mapW, mapH);

  for (const key in tileStates[B]) {
    const st = tileStates[B][key];
    if (st === 1 || st === 2) {
      const [c,r] = key.split(",").map(Number);
      miniCtx.fillStyle = st === 1 ? "#F00" : "#000";
      miniCtx.fillRect(c * sx, r * sy, sx, sy);
    }
  }

  const dotX = (playerX + tileSize/2)/tileSize * sx,
        dotY = (playerY + tileSize/2)/tileSize * sy;
  miniCtx.fillStyle = "#0F0";
  miniCtx.beginPath();
  miniCtx.arc(dotX, dotY, 5, 0, 2*Math.PI);
  miniCtx.fill();
}

function drawPlayer(x, y, username, img) {
  const r  = tileSize * 0.4,
        cx = x + tileSize/2,
        cy = y + tileSize/2;
  if (img && img.complete) {
    ctx.save();
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, 2*Math.PI);
      ctx.clip();
      ctx.drawImage(img, cx-r, cy-r, r*2, r*2);
    ctx.restore();
  } else {
    ctx.fillStyle = "#3498db";
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, 2*Math.PI);
    ctx.fill();
  }
  ctx.strokeStyle = "#31e700";
  ctx.lineWidth   = 1;
  ctx.beginPath();
  ctx.arc(cx, cy, r+1, 0, 2*Math.PI);
  ctx.stroke();

  ctx.fillStyle = "#31e700";
  ctx.font      = "16px Arial";
  ctx.textAlign = "center";
  ctx.fillText(username, cx, cy - r - 10);
}

function addChatMessage(msg) {
  const d = document.createElement("div");
  d.textContent = msg;
  chatLog.appendChild(d);
  chatLog.scrollTop = chatLog.scrollHeight;
}

// ─── PAINT CURRENT CELL ────────────────────────────────────────────────────
setInterval(() => {
  const col = Math.floor((playerX + tileSize/2)/tileSize),
        row = Math.floor((playerY + tileSize/2)/tileSize),
        key = `${col},${row}`;
  const b   = playerBoardLevel;
  const st  = tileStates[b][key] || 0;

  if (st === 2) {
    socket.emit("reset");
  } else {
    socket.emit("tile", { key, board: b });
  }
}, 100);

// ─── RE-EMIT ALL RED TILES EVERY SECOND ─────────────────────────────────────
setInterval(() => {
  for (let b = 1; b <= 3; b++) {
    for (const key of activeRedTiles[b]) {
      socket.emit("tile", { key, board: b });
    }
  }
}, 1000);

function gameLoop() {
  update();
  draw();
  requestAnimationFrame(gameLoop);
}
