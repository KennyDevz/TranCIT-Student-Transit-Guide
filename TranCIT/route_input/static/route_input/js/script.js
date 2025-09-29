document.getElementById("routeForm").addEventListener("submit", function (e) {
  let valid = true;

  // Clear old errors
  document.querySelectorAll(".error").forEach(el => el.textContent = "");

  const origin = this.origin.value.trim();
  const destination = this.destination.value.trim();
  const transportType = this.transport_type.value;
  const fare = this.fare.value;

  if (!origin) {
    document.getElementById("error-origin").textContent = "Origin is required.";
    valid = false;
  }

  if (!destination) {
    document.getElementById("error-destination").textContent = "Destination is required.";
    valid = false;
  }

  if (!transportType) {
    document.getElementById("error-transport").textContent = "Please select a transportation type.";
    valid = false;
  }

  if (fare && fare < 0) {
    document.getElementById("error-fare").textContent = "Fare cannot be negative.";
    valid = false;
  }

  if (!valid) e.preventDefault();
});
