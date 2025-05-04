console.log("play.js loaded");
let myAliveSeconds = 0;

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
      gridCols = 100,
      gridRows = 100,
      gridWidth  = tileSize * gridCols,
      gridHeight = tileSize * gridRows;

let playerX = gridWidth/2,
    playerY = gridHeight/2;
let hasSpawned = false;
let cameraX = 0,
    cameraY = 0;
let keys = {},
    playerSpeed = 3;
let avatarImg = null;
let tileStates = {1:{},2:{},3:{}};
let otherPlayers = {};
let playerBoardLevel = 1;
let gameStarted = false;
let isEliminated = false;
let winnerName = '';
const avatarCache    = {};
const activeRedTiles = {1: new Set(), 2: new Set(), 3: new Set()};

// Sprinting logic variables (already declared somewhere above)
let maxStamina = 150;
let stamina = maxStamina;
let sprinting = false;
let sprintSpeed = 6;
let staminaDrainRate = 1;
let staminaRegenRate = 0.25;

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

// Configuration
const MIN_PLAYERS = 2;
const COUNTDOWN_SECONDS = 10;

// Lobby state
let lobbyCount = 0

// Grab lobby DOM nodes
const lobbyOverlay      = document.getElementById("lobby-overlay");
const lobbyPlayerList   = document.getElementById("lobby-player-list");
const lobbyCountdownEl  = document.getElementById("lobby-countdown");

// Handle server “lobby” broadcasts
socket.on("lobby", data => {
  const players = data.players;
  lobbyPlayerList.innerHTML = "";
  players.forEach(name => {
    const li = document.createElement("li");
    li.textContent = name;
    lobbyPlayerList.appendChild(li);
  });

  // if too few players, show how many more
  if (players.length < MIN_PLAYERS) {
    lobbyCountdownEl.textContent = `Waiting… (${MIN_PLAYERS - players.length} more)`;
  }
  // otherwise, do nothing – the server's countdown events will update the number
});

// Hide overlay & kick off gameLoop if not already started
function hideLobby() {
  lobbyOverlay.classList.add("hidden");
  if (!gameStarted) {  
    socket.emit("rejoin");   // rejoin logic, if you want fresh init
    // the server’s next "game_start" can then trigger gameLoop()
  }
}

// (You can choose instead to rely on server’s "game_start" event as you already have)
socket.on("game_start", () => {
  hideLobby();
  if (!gameStarted) {
    gameStarted = true;
    gameLoop();
  }
});

socket.on("connect",    () => console.log("Socket connected:", socket.id));
socket.on("disconnect", () => console.log("Socket disconnected"));
socket.on("eliminated", () => {
  isEliminated = true;
});
socket.on("victory", data => {
  winnerName = data.username;
  if (isEliminated) {
      alert(`🎉 ${winnerName} won the game!`);
  } else {
    alert("🎉 Congratulations, you won!");
  }
  window.location.href = '/';
});

socket.on("countdown", data => {
  // 1) Lobby countdown (only update if we're still in the lobby view)
  if (!lobbyOverlay.classList.contains("hidden")) {
    if (data.time > 0) {
      lobbyCountdownEl.textContent = data.time;
    } else {
      // server just hit zero → hide the lobby for everyone
      hideLobby();
    }
  }

  // 2) (Optional) in‑game countdown display
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
  const { key, state, board, username:username } = msg;
  if (state === 0) {
    delete tileStates[board][key];
    activeRedTiles[board].delete(key);
  } else {
    tileStates[board][key] = state;
    if (state === 1) {
      if (!activeRedTiles[board].has(key)){
      activeRedTiles[board].add(key);
      if(window.PLAYER_USERNAME === username) {
        socket.emit("stepped-on-tile", {username: username});
      }
    }}

    else activeRedTiles[board].delete(key);
  }
});

// ─── PLAYER LIST ───────────────────────────────────────────────────────────
socket.on("players", msg => {
  otherPlayers = {};
  for (const id in msg.players) {
    const d = msg.players[id];

    if (id === socket.id) {
      // if (playerX === gridWidth/2) {
      //   playerX = d.x;
      // }
      // if (playerY === gridHeight/2) {
      //   playerY = d.y;
      // }
      if(!hasSpawned) {
        playerX = d.x;
        playerY = d.y;
        hasSpawned = true;
      }


      playerBoardLevel = d.board_level;

      // Update survival time based on server
      myAliveSeconds = d.alive_seconds || 0;

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
socket.on("game_reset", () => {
  gameStarted = false;
  hasSpawned = false;
  tileStates = {1:{},2:{},3:{}};
  otherPlayers = {};
  socket.emit("rejoin");
});

socket.on("chat", msg => addChatMessage(msg.text));

socket.on("top-players", data => {
  const list = document.getElementById("leaderboard-list");
  list.innerHTML = "";
  for (const player of data) {
    const li = document.createElement("li");
    li.textContent = `${player.username}: ${player.seconds}s`;
    list.appendChild(li);
  }
});

socket.on("time-until-reset", data => {
  const el = document.getElementById("reset-seconds");
  if (el) {
    el.textContent = data.seconds;
  }
});

// ─── MOVE + EMIT ──────────────────────────────────────────────────────────
let lastEmit = 0;
function update() {
  if (isEliminated) return;
  let dx = 0, dy = 0;

  // Always fresh movement input every frame
  if (keys.ArrowUp    /*|| keys.w*/) dy -= 1;
  if (keys.ArrowDown  /*|| keys.s*/) dy += 1;
  if (keys.ArrowLeft  /*|| keys.a*/) dx -= 1;
  if (keys.ArrowRight /*|| keys.d*/) dx += 1;

  const holdingShift = keys.Shift || keys.ShiftLeft || keys.ShiftRight;
  const moving = dx !== 0 || dy !== 0;

  // Handle sprinting purely on movement + shift
  if (moving && holdingShift && stamina > 0) {
    sprinting = true;
    stamina -= staminaDrainRate;
    if (stamina < 0) stamina = 0;
  } else {
    sprinting = false;
    if (!holdingShift) {
      stamina += staminaRegenRate;
      if (stamina > maxStamina) stamina = maxStamina;
    }
  }

  const currentSpeed = sprinting ? sprintSpeed : playerSpeed;

  if (moving) {
    // Normalize diagonal movement
    if (dx !== 0 && dy !== 0) {
      const factor = Math.sqrt(0.5);
      dx *= factor;
      dy *= factor;
    }

    // Move player based on current dx, dy, and speed
    playerX += dx * currentSpeed;
    playerY += dy * currentSpeed;

    // Clamp player inside the map
    playerX = Math.max(0, Math.min(playerX, gridWidth  - tileSize));
    playerY = Math.max(0, Math.min(playerY, gridHeight - tileSize));
  }

  // Update camera
  cameraX = Math.max(0, Math.min(playerX + tileSize/2 - canvas.width/2,
                                 gridWidth  - canvas.width));
  cameraY = Math.max(0, Math.min(playerY + tileSize/2 - canvas.height/2,
                                 gridHeight - canvas.height));

  // Emit movement update periodically
  const now = Date.now();
  if (now - lastEmit > 100) {
    socket.emit("move", { x: playerX, y: playerY });
    lastEmit = now;
  }

  // Smooth other players
  for (const id in otherPlayers) {
    const p = otherPlayers[id], s = 0.1;
    p.x += (p.targetX - p.x) * s;
    p.y += (p.targetY - p.y) * s;
  }
}

// ─── DRAW LOOP ─────────────────────────────────────────────────────────────
function draw() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
   if (isEliminated) {
    // Show elimination message
    ctx.fillStyle = "rgba(0, 0, 0, 0.7)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.fillStyle = "#FF0000";
    ctx.font = "bold 48px Arial";
    ctx.textAlign = "center";
    ctx.fillText("ELIMINATED", canvas.width/2, canvas.height/2 - 30);

    ctx.fillStyle = "#FFFFFF";
    ctx.font = "24px Arial";
    ctx.fillText("STAY TO SEE WHO WINS", canvas.width/2, canvas.height/2 + 30);

    if (winnerName) {
      ctx.fillStyle = "#FFFF00";
      ctx.font = "36px Arial";
      ctx.fillText(`${winnerName} WON!`, canvas.width/2, canvas.height/2 + 100);
    }
    return;
  }
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

      if(p.board_level === playerBoardLevel && !p.eliminated) {
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
  drawStaminaBar(ctx);
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

function drawStaminaBar(ctx) {
  const barWidth = 200;
  const barHeight = 20;
  const padding = 20;

  const staminaRatio = stamina / maxStamina;

  // Position at bottom-right corner
  const x = canvas.width - barWidth - padding;
  const y = canvas.height - barHeight - padding;

  // Background (gray)
  ctx.fillStyle = "#555";
  ctx.fillRect(x, y, barWidth, barHeight);

  // Stamina bar (green or red)
  ctx.fillStyle = staminaRatio > 0.3 ? "#00FF00" : "#FF0000";
  ctx.fillRect(x, y, barWidth * staminaRatio, barHeight);

  // Border
  ctx.strokeStyle = "#000";
  ctx.lineWidth = 2;
  ctx.strokeRect(x, y, barWidth, barHeight);
}

// ─── PAINT CURRENT CELL ────────────────────────────────────────────────────
setInterval(() => {
  const col = Math.floor((playerX + tileSize/2)/tileSize),
        row = Math.floor((playerY + tileSize/2)/tileSize),
        key = `${col},${row}`;
  const b   = playerBoardLevel;
  const st  = tileStates[b][key] || 0;
  const username = window.PLAYER_USERNAME

  if (st === 2) {
    socket.emit("reset");
  } else {
    socket.emit("tile", { key, board: b, username: username });
  }
}, 100);

// ─── RE-EMIT ALL RED TILES EVERY SECOND ─────────────────────────────────────
setInterval(() => {
  for (let b = 1; b <= 3; b++) {
    for (const key of activeRedTiles[b]) {
      socket.emit("tile", { key, board: b, username: null});
    }
  }
}, 1000);

// function updateSurvivalTimerUI() {
//   const el = document.getElementById("timer-seconds");
//   if (el) {
//     el.textContent = myAliveSeconds;
//   }
//   requestAnimationFrame(updateSurvivalTimerUI);
// }

function gameLoop() {
  update();
  draw();
  requestAnimationFrame(gameLoop);
}
