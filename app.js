const messagesEl = document.querySelector("#messages");
const formEl = document.querySelector("#chat-form");
const inputEl = document.querySelector("#message-input");
const requirementsEl = document.querySelector("#requirements-list");
const degreeEl = document.querySelector("#selected-degree");
const courseListEl = document.querySelector("#course-list");
const courseSearchEl = document.querySelector("#course-search");
const resetButton = document.querySelector("#reset-chat");

let conversationId = localStorage.getItem("conversationId") || "";

const starterMessage =
  "Hi, I’m ready to help you plan your degree @ UW! How would you like your UW degree to look like?";

function setSelectedDegree(name) {
  const matchingOption = [...degreeEl.options].find((option) => option.value === name);
  degreeEl.value = matchingOption?.value || "Computer Science (BCS)";
}

function addMessage(role, content) {
  const message = document.createElement("article");
  message.className = `message ${role}`;
  message.textContent = content;
  messagesEl.append(message);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function renderRequirements(degree) {
  setSelectedDegree(degree?.name);
  requirementsEl.innerHTML = "";

  if (!degree?.requirements?.length) {
    requirementsEl.innerHTML = '<p class="muted">Requirements will appear after the API loads.</p>';
    return;
  }

  for (const requirement of degree.requirements) {
    const card = document.createElement("article");
    card.className = "requirement";
    card.innerHTML = `
      <strong>${requirement.category} · ${requirement.credits} credits</strong>
      <p>${requirement.details}</p>
    `;
    requirementsEl.append(card);
  }
}

function renderCourses(courses) {
  courseListEl.innerHTML = "";

  for (const course of courses) {
    const courseId = course.course_id || course.code || "";
    const title = course.title || "Course details unavailable";
    const credits = course.credits ?? "Unknown";
    const courseType = course.ctype || "Course";
    const description = course.description || "Description unavailable.";
    const termPill = course.term ? `<span class="pill term">Term ${course.term}</span>` : "";

    const card = document.createElement("article");
    card.className = "course-card";
    card.innerHTML = `
      <strong>${courseId} · ${title}</strong>
      <p>${description}</p>
      <div class="course-meta">
        <span class="pill credits">${credits} credits</span>
        <span class="pill type">${courseType}</span>
        ${termPill}
      </div>
    `;
    courseListEl.append(card);
  }
}

async function loadDegrees() {
  const response = await fetch("/api/degrees");
  const data = await response.json();
  renderRequirements(data.degrees[0]);
}

async function loadCourses(search = "") {
  const params = search ? `?q=${encodeURIComponent(search)}` : "";
  const response = await fetch(`/api/courses${params}`);
  const data = await response.json();
  renderCourses(data.courses);
}

async function sendMessage(message) {
  const submitButton = formEl.querySelector("button");
  submitButton.disabled = true;

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversationId, message }),
    });

    if (!response.ok) {
      throw new Error("Chat API request failed");
    }

    const data = await response.json();
    conversationId = data.conversationId;
    localStorage.setItem("conversationId", conversationId);
    addMessage("assistant", data.message);

    if (data.degree?.requirements) {
      renderRequirements(data.degree);
    } else if (data.degree) {
      setSelectedDegree(data.degree.name);
    }

    if (data.suggestedCourses?.length) {
      renderCourses(data.suggestedCourses);
    }
  } catch (error) {
    addMessage("assistant", "I could not reach the planning API. Check that the Python backend is running, then try again.");
  } finally {
    submitButton.disabled = false;
    inputEl.focus();
  }
}

formEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = inputEl.value.trim();
  if (!message) return;

  addMessage("user", message);
  inputEl.value = "";
  await sendMessage(message);
});

courseSearchEl.addEventListener("input", (event) => {
  loadCourses(event.target.value.trim());
});

resetButton.addEventListener("click", () => {
  conversationId = "";
  localStorage.removeItem("conversationId");
  messagesEl.innerHTML = "";
  addMessage("assistant", starterMessage);
});

addMessage("assistant", starterMessage);
loadDegrees();
loadCourses();
