// Get canvas and context
const canvas = document.getElementById("myCanvas");
const ctx = canvas.getContext("2d");

// Define the object to move (a square in this case)
let square = {
  x: 100,
  y: 100,
  size: 30,
  speed: 5
};

// Function to update the position of the square based on key presses
function updatePosition(e) {
  if (e.key === "ArrowUp" || e.key === "w") {
    square.y -= square.speed;  // Move up
  }
  if (e.key === "ArrowDown" || e.key === "s") {
    square.y += square.speed;  // Move down
  }
  if (e.key === "ArrowLeft" || e.key === "a") {
    square.x -= square.speed;  // Move left
  }
  if (e.key === "ArrowRight" || e.key === "d") {
    square.x += square.speed;  // Move right
  }
}

// Function to draw the square on the canvas
function draw() {
  // Clear the canvas
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // Draw the square
  ctx.fillStyle = "blue";
  ctx.fillRect(square.x, square.y, square.size, square.size);
}

// Event listener for keydown events
document.addEventListener("keydown", updatePosition);

// Function to continuously animate the movement of the square
function animate() {
  draw();
  requestAnimationFrame(animate);  // Keep calling the animate function for continuous movement
}

// Start the animation loop
animate();