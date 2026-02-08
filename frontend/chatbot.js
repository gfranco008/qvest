const chatWindow = document.getElementById("chatWindow");
const chatInput = document.getElementById("chatInput");
const sendButton = document.getElementById("sendButton");

const API_BASE = "http://localhost:8000";
const starterTips = [
  "Try: \"Suggest books for a grade 5 student who likes mystery.\"",
  "Try: \"What are good read-alikes for The Brave Map?\"",
  "Try: \"Give me a short pitch for a library mystery book.\"",
];

function addMessage(text, sender = "user") {
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${sender}`;
  bubble.textContent = text;
  chatWindow.appendChild(bubble);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

async function fetchResponse(prompt) {
  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: prompt }),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Chat request failed");
  }

  const data = await response.json();
  return data.reply;
}

function sendMessage() {
  const text = chatInput.value.trim();
  if (!text) return;
  addMessage(text, "user");
  chatInput.value = "";
  fetchResponse(text)
    .then((reply) => addMessage(reply, "bot"))
    .catch((error) => {
      addMessage(`Error: ${error.message}`, "bot");
    });
}

sendButton.addEventListener("click", sendMessage);
chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") sendMessage();
});

starterTips.forEach((tip) => addMessage(tip, "bot"));
