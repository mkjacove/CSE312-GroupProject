// Play.js

const playerColor = "#" + Math.floor(Math.random() * 16777215).toString(16);

document.addEventListener("DOMContentLoaded", function () {
  const grid = document.getElementById("grid-container");
  const gridSize = 10;
  let playerPosition = { x: 0, y: 0 };

  // Create grid cells
  for (let i = 0; i < gridSize * gridSize; i++) {
    const cell = document.createElement("div");
    cell.classList.add("grid-cell");
    grid.appendChild(cell);
  }

  const updatePlayerPosition = () => {
    const cells = grid.querySelectorAll(".grid-cell");

    // Reset all cells
    cells.forEach(cell => {
      cell.classList.remove("player");
      cell.style.backgroundColor = "#4a5568"; // Your default grid cell color
    });

    const index = playerPosition.y * gridSize + playerPosition.x;

    // Add the "player" class to the current cell
    const playerCell = cells[index];
    playerCell.style.backgroundColor = playerColor;
    playerCell.classList.add("player");
};

  // Initial player position
  updatePlayerPosition();

  document.addEventListener("keydown", (event) => {
    const key = event.key.toLowerCase(); // normalize to lowercase
    switch (key) {
      case "w": // up
        if (playerPosition.y > 0) {
          playerPosition.y -= 1;
          updatePlayerPosition();
        }
        break;
      case "a": // left
        if (playerPosition.x > 0) {
          playerPosition.x -= 1;
          updatePlayerPosition();
        }
        break;
      case "s": // down
        if (playerPosition.y < gridSize - 1) {
          playerPosition.y += 1;
          updatePlayerPosition();
        }
        break;
      case "d": // right
        if (playerPosition.x < gridSize - 1) {
          playerPosition.x += 1;
          updatePlayerPosition();
        }
        break;
    }
  });
});


