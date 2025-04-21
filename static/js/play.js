// play.js
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
  // fixed-size minimap
  miniMapCanvas.width  = 200;
  miniMapCanvas.height = 200;
}
window.addEventListener("resize", resizeCanvas);
resizeCanvas();

// --- game constants + state
const tileSize   = 50,
      gridCols   = 500,
      gridRows   = 500,
      gridWidth  = tileSize * gridCols,
      gridHeight = tileSize * gridRows;
let playerX = gridWidth/2,
    playerY = gridHeight/2;
let cameraX = 0,
    cameraY = 0;
let keys = {},
    playerSpeed = 5;
let avatarImg = null;
let tileStates = { 1: {}, 2: {}, 3: {} };   // per board
let otherPlayers = {};   // { sid: { x,y,username,avatarImg } }

// --- input handling
document.addEventListener("keydown", e => keys[e.key] = true);
document.addEventListener("keyup",   e => keys[e.key] = false);

// --- load avatar from globals
if (window.PLAYER_AVATAR) {
  avatarImg = new Image();
  avatarImg.src = `/images/${window.PLAYER_AVATAR}`;

  avatarImg.onerror = () => {
    console.error("Failed to load avatar image!");
    avatarImg = null;  // fallback to default circle
  };
}

// --- Socket.IO setup
const socket = io('/game', { transports: ['websocket'] });

socket.on("connect", () => {
  console.log("Socket connected:", socket.id);
});
socket.on("disconnect", () => {
  console.log("Socket disconnected");
});

socket.on("eliminated", (data) => {
    alert("You've been eliminated!");
    window.location.href = data.redirect;
});

// initial full‑board snapshot
socket.on('tile-init', data => {
  tileStates = { 1: {}, 2: {}, 3: {} }; // reset clean

  if (data.tileStates) {
    for (let boardNum in data.tileStates) {
      tileStates[boardNum] = data.tileStates[boardNum];
    }
  }
});

// one‑off tile updates
socket.on('tile-update', msg => {
  const currentBoard = getPlayerBoardLevel(); // Get current board level (1, 2, or 3)

  // Only update the current board
  if (msg.board === currentBoard) {
    if (msg.state === 0) {
      delete tileStates[currentBoard][msg.key];
    } else {
      tileStates[currentBoard][msg.key] = msg.state;
    }
    draw(); // Re-render tiles after update
  }
});


// players list (add/update/remove)
socket.on("players", msg => {
  otherPlayers = {};
  for (const id in msg.players) {
    if (id === socket.id) {
      playerX = msg.players[id].x;
      playerY = msg.players[id].y;
      continue;
    }
    const d = msg.players[id];
    const img = new Image();
    img.src = `/images/${d.avatar}`;
    otherPlayers[id] = { ...d, avatarImg: img };
  }
});

// optional chat handler
socket.on("chat", msg => addChatMessage(msg.text));

function getPlayerBoardLevel() {
  return otherPlayers[socket.id]?.board_level || 1;  // Default to board 1 if not found
}

// --- game update: movement + emit
function update() {
  let dx = 0, dy = 0;
  if (keys.ArrowUp || keys.w)    dy -= playerSpeed;
  if (keys.ArrowDown || keys.s)  dy += playerSpeed;
  if (keys.ArrowLeft || keys.a)  dx -= playerSpeed;
  if (keys.ArrowRight || keys.d) dx += playerSpeed;

  playerX = Math.max(0, Math.min(playerX + dx, gridWidth));
  playerY = Math.max(0, Math.min(playerY + dy, gridHeight));

  cameraX = Math.max(0, Math.min(playerX + tileSize/2 - canvas.width/2,
                                  gridWidth  - canvas.width));
  cameraY = Math.max(0, Math.min(playerY + tileSize/2 - canvas.height/2,
                                  gridHeight - canvas.height));

  socket.emit("move", { x: playerX, y: playerY });
}

// --- draw loop
function draw() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  ctx.save();
    ctx.translate(-cameraX, -cameraY);

    // Get current board level from server (you'll receive this via `players`)
    const currentBoard = getPlayerBoardLevel(); // This function returns player's current board level (1, 2, or 3)

    // draw tiles for the current board
    const startCol = Math.floor(cameraX / tileSize),
          endCol   = Math.ceil((cameraX + canvas.width)  / tileSize);
    const startRow = Math.floor(cameraY / tileSize),
          endRow   = Math.ceil((cameraY + canvas.height) / tileSize);

    for (let r = startRow; r < endRow; r++) {
      for (let c = startCol; c < endCol; c++) {
        const x = c * tileSize,
              y = r * tileSize,
              k = `${c},${r}`;
        const state = tileStates[currentBoard][k] || 0;  // Use the correct board's state

        ctx.fillStyle = state === 1  ? "#F00"  // Red for painted tiles
                       : state === 2 ? "#000"  // Black for the tiles that should cause progression
                       :               "#FFF"; // White for empty tiles

        ctx.fillRect(x, y, tileSize, tileSize);
        ctx.strokeStyle = "#CCC";
        ctx.strokeRect(x, y, tileSize, tileSize);
      }
    }

    // draw self (avatar)
    drawPlayer(playerX, playerY, window.PLAYER_USERNAME, avatarImg);

    // draw others (players)
    for (const id in otherPlayers) {
      const p = otherPlayers[id];
      drawPlayer(p.x, p.y, p.username, p.avatarImg);
    }
  ctx.restore();

  // --- draw minimap
  const cols   = gridCols,
        rows   = gridRows,
        mapW   = miniMapCanvas.width,
        mapH   = miniMapCanvas.height,
        scaleX = mapW / cols,
        scaleY = mapH / rows;
  miniCtx.clearRect(0, 0, mapW, mapH);

  // background
  miniCtx.fillStyle = "#FFF";
  miniCtx.fillRect(0, 0, mapW, mapH);

  // painted tiles (red=1, black=2)
  for (const key in tileStates[currentBoard]) {  // Filter by current board
    const [c, r] = key.split(',').map(Number),
          st     = tileStates[currentBoard][key];
    if (st === 1)       miniCtx.fillStyle = "#F00";
    else if (st === 2)  miniCtx.fillStyle = "#000";
    else                continue;
    miniCtx.fillRect(c * scaleX, r * scaleY, scaleX, scaleY);
  }

  // player dot (on minimap)
  const cellX = (playerX + tileSize / 2) / tileSize,
        cellY = (playerY + tileSize / 2) / tileSize;
  miniCtx.fillStyle = "#0F0";
  miniCtx.beginPath();
  miniCtx.arc(cellX * scaleX, cellY * scaleY, 5, 0, 2 * Math.PI);
  miniCtx.fill();
}


// draw a single player avatar+name (with border)
function drawPlayer(x, y, username, img) {
  const radius = tileSize * 0.4,
        cx = x + tileSize/2,
        cy = y + tileSize/2;

  // avatar circle
  if (img && img.complete) {
    ctx.save();
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, 2*Math.PI);
      ctx.clip();
      ctx.drawImage(img, cx-radius, cy-radius, radius*2, radius*2);
    ctx.restore();
  } else {
    ctx.fillStyle = "#3498db";
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, 2*Math.PI);
    ctx.fill();
  }

  // Draw circle border
  ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, radius + 1, 0, Math.PI * 2); // slightly larger
    ctx.closePath();
    ctx.strokeStyle = "#31e700"; // border color
    ctx.lineWidth = 1;
    ctx.stroke();
  ctx.restore();

  // username label
  ctx.fillStyle = "#31e700";
  ctx.font = "16px Arial";
  ctx.textAlign = "center";
  ctx.fillText(username, cx, cy - radius - 10);
}

// helper to append chat messages
function addChatMessage(msg) {
  const div = document.createElement("div");
  div.textContent = msg;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

// emit painting every 100ms
setInterval(() => {
  const col = Math.floor((playerX + tileSize/2) / tileSize);
  const row = Math.floor((playerY + tileSize/2) / tileSize);
  const key = `${col},${row}`;

  const currentBoard = getPlayerBoardLevel(); // <--- fix: get current board
  const state = tileStates[currentBoard][key] || 0; // <--- fix: access correct board's tile

  if (state === 2) {
    // You stepped on a black tile!
    socket.emit("reset"); // <--- tell server to reset
    return; // stop here so you don't keep painting
  }

  socket.emit("tile", { key });
}, 100);

// start game loop
function gameLoop() {
  update();
  draw();
  requestAnimationFrame(gameLoop);
}
gameLoop();
