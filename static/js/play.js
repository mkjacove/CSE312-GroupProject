// ----------------------------
// Configuration and Global Setup
// ----------------------------

// Main game canvas and context.
const canvas = document.getElementById("gameCanvas");
const ctx = canvas.getContext("2d");

// Resize main canvas to fill entire viewport.
function resizeCanvas() {
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
}
window.addEventListener('resize', resizeCanvas);
resizeCanvas();

// Mini map canvas and context – fixed square (200x200).
const miniMapCanvas = document.getElementById("miniMapCanvas");
const miniCtx = miniMapCanvas.getContext("2d");

// Grid settings.
const gridCols = 500;
const gridRows = 500;
const tileSize = 50;           // Each tile is 50x50 pixels.
const gridWidth = gridCols * tileSize;
const gridHeight = gridRows * tileSize;

// Player settings.
// The player occupies exactly one tile.
const playerSize = tileSize;
let playerX = gridWidth / 2;  // Start at the center of the grid.
let playerY = gridHeight / 2;
const playerSpeed = 5;

// Generate a random color for the player's main representation.
function getRandomColor() {
  const letters = "0123456789ABCDEF";
  let color = "#";
  for (let i = 0; i < 6; i++) {
    color += letters[Math.floor(Math.random() * 16)];
  }
  return color;
}
let playerColor = getRandomColor();

// Camera/viewport settings.
let cameraX = 0;
let cameraY = 0;

// Keyboard input tracking.
let keys = {};
document.addEventListener("keydown", (e) => { keys[e.key] = true; });
document.addEventListener("keyup", (e) => { keys[e.key] = false; });

// ----------------------------
// Tick System for TNT Run Logic
// ----------------------------

// We'll track triggered tiles in an object keyed as "col,row".
// Each entry holds an object: { state, timer } where:
//   state: 1 = "red" (active trigger), 2 = "dead" (tile disappeared, drawn black)
//   timer: counts down ticks.
let tileStates = {};

// Duration (in ticks) the tile remains red before turning dead.
// 1 second at 20 ticks-per-second = 20 ticks.
const RED_DURATION = 20;

// Tick function runs 20 times per second.
function tick() {
  // Identify the tile currently under the player's center.
  let playerTileCol = Math.floor(playerX / tileSize);
  let playerTileRow = Math.floor(playerY / tileSize);
  let key = playerTileCol + "," + playerTileRow;
  if (!tileStates[key]) {
    // Mark this tile as triggered (red) if not already triggered.
    tileStates[key] = { state: 1, timer: RED_DURATION };
  }
  
  // Update all triggered tiles.
  for (let tKey in tileStates) {
    let tile = tileStates[tKey];
    if (tile.state === 1) {  // In the red phase.
      tile.timer--;
      if (tile.timer <= 0) {
        tile.state = 2;    // Transition to dead (black).
      }
    }
    // Once in state 2, the tile remains dead (black).
  }
}
// Start tick system at 20 TPS.
setInterval(tick, 50);

// ----------------------------
// Fullscreen Setup
// ----------------------------
// Apply fullscreen to the container so that both canvases remain visible.
document.getElementById("fullscreen-btn").addEventListener("click", () => {
  const container = document.getElementById("canvas-container");
  if (document.fullscreenElement) {
    document.exitFullscreen();
  } else {
    container.requestFullscreen().catch(err => {
      console.error(`Error attempting fullscreen: ${err.message}`);
    });
  }
});

// ----------------------------
// Game Loop and Rendering Routines
// ----------------------------

function update() {
  let dx = 0, dy = 0;
  if (keys["ArrowUp"] || keys["w"]) dy -= playerSpeed;
  if (keys["ArrowDown"] || keys["s"]) dy += playerSpeed;
  if (keys["ArrowLeft"] || keys["a"]) dx -= playerSpeed;
  if (keys["ArrowRight"] || keys["d"]) dx += playerSpeed;
  
  let newPlayerX = playerX + dx;
  let newPlayerY = playerY + dy;
  newPlayerX = Math.max(0, Math.min(newPlayerX, gridWidth - playerSize));
  newPlayerY = Math.max(0, Math.min(newPlayerY, gridHeight - playerSize));
  playerX = newPlayerX;
  playerY = newPlayerY;
  
  const viewWidth = canvas.width;
  const viewHeight = canvas.height;
  const margin = 100;  // Margin to auto-scroll.
  
  if (playerX - cameraX < margin) {
    cameraX = Math.max(0, playerX - margin);
  } else if (playerX - cameraX > viewWidth - margin - playerSize) {
    cameraX = Math.min(gridWidth - viewWidth, playerX - viewWidth + margin + playerSize);
  }
  if (playerY - cameraY < margin) {
    cameraY = Math.max(0, playerY - margin);
  } else if (playerY - cameraY > viewHeight - margin - playerSize) {
    cameraY = Math.min(gridHeight - viewHeight, playerY - viewHeight + margin + playerSize);
  }
}
let avatarImg = null;
if (window.PLAYER_AVATAR) {
  avatarImg = new Image();
  avatarImg.src = "/images/" + window.PLAYER_AVATAR;
}

let username = null;
if(window.PLAYER_USERNAME) {
  username = window.PLAYER_USERNAME;
}

fetch("/api/users/@me")
  .then(res => res.json())
  .then(user => {
    if (user && user.avatar) {
      window.PLAYER_AVATAR = user.avatar;

      // Load avatar image once user info is available
      avatarImg = new Image();
      avatarImg.src = "/images/" + window.PLAYER_AVATAR;
    }

    if (user && user.username) {
      username = user.username;
    }

  });

function draw() {
  const viewWidth = canvas.width;
  const viewHeight = canvas.height;
  
  // Draw visible grid tiles.
  const startCol = Math.floor(cameraX / tileSize);
  const endCol = Math.min(gridCols, Math.floor((cameraX + viewWidth) / tileSize) + 1);
  const startRow = Math.floor(cameraY / tileSize);
  const endRow = Math.min(gridRows, Math.floor((cameraY + viewHeight) / tileSize) + 1);
  
  // For each visible tile, determine its color.
  for (let row = startRow; row < endRow; row++) {
    for (let col = startCol; col < endCol; col++) {
      const tileX = col * tileSize - cameraX;
      const tileY = row * tileSize - cameraY;
      let key = col + "," + row;
      // Default tile (active) is white.
      let fillColor = "#ffffff";
      if (tileStates[key]) {
        if (tileStates[key].state === 1) {
          fillColor = "#FF0000"; // red when triggered.
        } else if (tileStates[key].state === 2) {
          fillColor = "#000000"; // dead blocks are black.
        }
      }
      ctx.fillStyle = fillColor;
      ctx.fillRect(tileX, tileY, tileSize, tileSize);
      
      // Draw grid lines.
      ctx.strokeStyle = "#cccccc";
      ctx.lineWidth = 1;
      ctx.strokeRect(tileX, tileY, tileSize, tileSize);
    }
  }

  // Draw the player's avatar as a circle.
  const playerScreenX = playerX - cameraX + playerSize / 2;
  const playerScreenY = playerY - cameraY + playerSize / 2;

  // If the avatar URL is available, draw the image as the player's avatar.
  if (avatarImg && avatarImg.complete) {
  const avatarRadius = playerSize / 2;
  // Draw circle border
  ctx.save();
  ctx.beginPath();
  ctx.arc(playerScreenX, playerScreenY, avatarRadius, 0, Math.PI * 2); // Slightly bigger radius for border
  ctx.closePath();
  ctx.strokeStyle = "#31e700"; // Border color
  ctx.lineWidth = 1; // Optional: Thickness of the border
  ctx.stroke();
  ctx.restore();

  // Draw avatar image clipped in a circle
  ctx.save();
  ctx.beginPath();
  ctx.arc(playerScreenX, playerScreenY, avatarRadius, 0, Math.PI * 2);
  ctx.closePath();
  ctx.clip();
  ctx.drawImage(avatarImg, playerScreenX - avatarRadius, playerScreenY - avatarRadius, playerSize, playerSize);
  ctx.restore();
} else {
  // Fallback circle
  ctx.fillStyle = playerColor;
  ctx.beginPath();
  ctx.arc(playerScreenX, playerScreenY, playerSize / 2, 0, Math.PI * 2);
  ctx.fill();
}
  // Add the username if it exists
  if (username) {
  ctx.font = "16px Arial";
  ctx.fillStyle = "#31e700";
  ctx.textAlign = "center";
  ctx.fillText(username, playerScreenX, playerScreenY - playerSize / 2 - 10);
}

  // ----------------------------
  // Draw the Mini Map
  // ----------------------------
  const miniWidth = miniMapCanvas.width;
  const miniHeight = miniMapCanvas.height;
  const scaleX = miniWidth / gridWidth;
  const scaleY = miniHeight / gridHeight;

  // Clear and fill mini map.
  miniCtx.fillStyle = "#ffffff";
  miniCtx.fillRect(0, 0, miniWidth, miniHeight);

  // Draw triggered tiles in the mini map.
  for (let tKey in tileStates) {
    let parts = tKey.split(",");
    let col = parseInt(parts[0]);
    let row = parseInt(parts[1]);
    let tileState = tileStates[tKey].state;
    let miniFill = (tileState === 1) ? "#FF0000" : "#000000";
    miniCtx.fillStyle = miniFill;
    miniCtx.fillRect(col * tileSize * scaleX, row * tileSize * scaleY, tileSize * scaleX, tileSize * scaleY);
  }

  // Draw the player's position on the mini map as red.
  miniCtx.fillStyle = "#FF0000";
  miniCtx.fillRect(playerX * scaleX, playerY * scaleY, tileSize * scaleX, tileSize * scaleY);

  // Draw the main viewport on the mini map with a red rectangle.
  miniCtx.strokeStyle = "#FF0000";
  miniCtx.lineWidth = 1;
  miniCtx.strokeRect(cameraX * scaleX, cameraY * scaleY, viewWidth * scaleX, viewHeight * scaleY);
}
function gameLoop() {
  update();

  draw();
  requestAnimationFrame(gameLoop);
}

gameLoop();
