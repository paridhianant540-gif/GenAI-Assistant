// TRUEAILAB RAG Chat Assistant - Core State & Client Manager

// Configurable API base url. Change if deployed, defaults to current host port 8000
// Smart API base resolver: resolves to local port 8000 in dev, or relative host in prod
const API_BASE = 
    window.location.origin === "null" || 
    window.location.protocol === "file:" || 
    window.location.port === "3000" 
        ? "http://127.0.0.1:8000" 
        : window.location.origin;

let sessionsParsed = [];
try {
    const rawSessions = localStorage.getItem("rag_sessions");
    if (rawSessions) {
        sessionsParsed = JSON.parse(rawSessions);
        if (!Array.isArray(sessionsParsed)) {
            sessionsParsed = [];
        }
    }
} catch (e) {
    console.error("Error parsing sessions from localStorage:", e);
    sessionsParsed = [];
}

let state = {
    sessionId: localStorage.getItem("rag_session_id") || generateId(),
    token: localStorage.getItem("rag_jwt_token") || null,
    username: localStorage.getItem("rag_username") || null,
    sessions: sessionsParsed,
    provider: localStorage.getItem("rag_provider") || "gemini",
    threshold: parseFloat(localStorage.getItem("rag_threshold")) || 0.65,
};

// ==========================================
// DOM Elements Initialization
// ==========================================
document.addEventListener("DOMContentLoaded", () => {
    // Session lists
    if (!state.sessions.includes(state.sessionId)) {
        state.sessions.push(state.sessionId);
        saveState();
    }
    
    // Wire UI events
    setupEventHandlers();
    
    // Sync DOM with loaded state
    syncConfigUI();
    syncAuthUI();
    renderSessionList();
    
    // Initial fetch of corpus
    fetchCorpus();
    
    // Load current chat history
    loadSessionHistory(state.sessionId);
});

// ==========================================
// Helper Functions
// ==========================================
function generateId() {
    return "session_" + Math.random().toString(36).substring(2, 9);
}

function saveState() {
    localStorage.setItem("rag_session_id", state.sessionId);
    localStorage.setItem("rag_sessions", JSON.stringify(state.sessions));
    localStorage.setItem("rag_provider", state.provider);
    localStorage.setItem("rag_threshold", state.threshold.toString());
    if (state.token) {
        localStorage.setItem("rag_jwt_token", state.token);
        localStorage.setItem("rag_username", state.username);
    } else {
        localStorage.removeItem("rag_jwt_token");
        localStorage.removeItem("rag_username");
    }
}

function getHeaders() {
    const headers = {
        "Content-Type": "application/json"
    };
    if (state.token) {
        headers["Authorization"] = `Bearer ${state.token}`;
    }
    return headers;
}

// ==========================================
// UI Synchronization
// ==========================================
function syncConfigUI() {
    document.getElementById("provider-select").value = state.provider;
    document.getElementById("threshold-slider").value = state.threshold;
    document.getElementById("threshold-val").innerText = state.threshold.toFixed(2);
    document.getElementById("active-model-badge").innerText = state.provider === "gemini" ? "Gemini-1.5-Flash" : "GPT-4o-Mini";
}

function syncAuthUI() {
    const loggedOutSection = document.getElementById("auth-logged-out");
    const loggedInSection = document.getElementById("auth-logged-in");
    
    if (state.token && state.username) {
        loggedOutSection.classList.add("hidden");
        loggedInSection.classList.remove("hidden");
        document.getElementById("display-username").innerText = state.username;
        document.querySelector(".avatar").innerText = state.username.substring(0, 1).toUpperCase();
    } else {
        loggedOutSection.classList.remove("hidden");
        loggedInSection.classList.add("hidden");
        document.getElementById("auth-username").value = "";
        document.getElementById("auth-password").value = "";
    }
}

// ==========================================
// Event Routing
// ==========================================
function setupEventHandlers() {
    // Form handlers
    document.getElementById("chat-form").addEventListener("submit", handleSendMessage);
    document.getElementById("login-form").addEventListener("submit", handleLogin);
    
    // Auth register button
    document.getElementById("btn-signup").addEventListener("click", handleRegister);
    document.getElementById("btn-logout").addEventListener("click", handleLogout);
    
    // Navigation handlers
    document.getElementById("btn-new-chat").addEventListener("click", startNewChat);
    document.getElementById("btn-clear-history").addEventListener("click", clearScreen);
    
    // Configuration handlers
    document.getElementById("provider-select").addEventListener("change", (e) => {
        state.provider = e.target.value;
        saveState();
        showToast(`Model provider changed to: ${state.provider === 'gemini' ? 'Google Gemini' : 'OpenAI GPT'}`);
        syncConfigUI();
    });
    
    document.getElementById("threshold-slider").addEventListener("input", (e) => {
        state.threshold = parseFloat(e.target.value);
        document.getElementById("threshold-val").innerText = state.threshold.toFixed(2);
    });
    
    document.getElementById("threshold-slider").addEventListener("change", () => {
        saveState();
        showToast(`Grounding threshold updated to: ${state.threshold.toFixed(2)}`);
    });
    
    // Sample query button click delegates
    document.querySelector(".chat-messages").addEventListener("click", (e) => {
        if (e.target.classList.contains("sample-query-btn")) {
            const query = e.target.innerText;
            document.getElementById("chat-input").value = query;
            document.getElementById("chat-form").requestSubmit();
        }
    });
}

// ==========================================
// Render Engine & Bubbles
// ==========================================
function renderSessionList() {
    const list = document.getElementById("session-list");
    list.innerHTML = "";
    
    state.sessions.slice().reverse().forEach((sess) => {
        const item = document.createElement("div");
        item.className = `session-item ${sess === state.sessionId ? "active" : ""}`;
        item.innerHTML = `
            <span class="sess-id">${sess}</span>
            <span class="sess-time">Active Session</span>
        `;
        item.addEventListener("click", () => {
            if (state.sessionId !== sess) {
                state.sessionId = sess;
                saveState();
                renderSessionList();
                document.getElementById("active-session-title").innerText = `Session: ${sess}`;
                loadSessionHistory(sess);
            }
        });
        list.appendChild(item);
    });
}

function appendMessage(role, content, tokens = 0) {
    const chatContainer = document.getElementById("chat-messages");
    
    // Remove welcome card if it exists
    const welcome = chatContainer.querySelector(".welcome-card");
    if (welcome) {
        welcome.remove();
    }
    
    const row = document.createElement("div");
    row.className = `msg-row ${role === 'user' ? 'user' : 'assistant'}`;
    
    const bubble = document.createElement("div");
    bubble.className = "msg-bubble";
    
    // Render markdown beautifully for assistant replies
    if (role === 'assistant') {
        bubble.innerHTML = marked.parse(content);
    } else {
        bubble.innerText = content;
    }
    
    const meta = document.createElement("div");
    meta.className = "msg-meta";
    
    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    let metaHTML = `<span>${timeStr}</span>`;
    
    if (role === 'assistant' && tokens > 0) {
        metaHTML += ` • <span class="badge font-xs">Tokens: ${tokens}</span>`;
    }
    
    meta.innerHTML = metaHTML;
    
    row.appendChild(bubble);
    chatContainer.appendChild(row);
    chatContainer.appendChild(meta);
    
    // Smooth auto scroll
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function clearScreen() {
    document.getElementById("chat-messages").innerHTML = `
        <div class="welcome-card">
            <span class="welcome-icon">⚡</span>
            <h2>Screen cleared</h2>
            <p>Ready for a fresh, grounded context inquiry. History remains saved on backend database.</p>
        </div>
    `;
    resetInspector();
}

// ==========================================
// RAG Inspector Visualizer
// ==========================================
function resetInspector() {
    document.getElementById("inspect-chunks-count").innerText = "0";
    document.getElementById("inspect-tokens-used").innerText = "0";
    
    const alertBox = document.getElementById("inspector-status-alert");
    alertBox.className = "alert-status alert-empty";
    alertBox.innerText = "No query parsed yet. Send a message to inspect vector similarity scores.";
    
    document.getElementById("inspector-chunks-container").innerHTML = `
        <div class="empty-state-chunks">
            <p>Ready to validate database lookup results and mathematical similarities.</p>
        </div>
    `;
}

function updateRAGInspector(chunks, tokensUsed, success) {
    document.getElementById("inspect-chunks-count").innerText = chunks.length;
    document.getElementById("inspect-tokens-used").innerText = tokensUsed;
    
    const alertBox = document.getElementById("inspector-status-alert");
    
    if (chunks.length === 0) {
        alertBox.className = "alert-status alert-fallback";
        alertBox.innerText = `GROUNDING FALLBACK TRIGGERED: No matches met threshold (${state.threshold.toFixed(2)}). All vectors discarded. LLM invocation bypassed.`;
        
        document.getElementById("inspector-chunks-container").innerHTML = `
            <div class="empty-state-chunks" style="border-color: rgba(239,68,68,0.3); color: #fecaca;">
                <p>Similarity search yielded 0 documents matching similarity threshold >= ${state.threshold.toFixed(2)}.</p>
            </div>
        `;
        return;
    }
    
    alertBox.className = "alert-status alert-retrieved";
    alertBox.innerText = `SUCCESS: Retrieved ${chunks.length} semantically matching documents exceeding similarity threshold ${state.threshold.toFixed(2)}. Generating context-grounded response.`;
    
    const container = document.getElementById("inspector-chunks-container");
    container.innerHTML = "";
    
    chunks.forEach((chunk, index) => {
        const score = chunk.score;
        let scoreClass = "low";
        if (score >= 0.75) scoreClass = "high";
        else if (score >= 0.65) scoreClass = "medium";
        
        const card = document.createElement("div");
        card.className = "chunk-inspect-card";
        
        const chunkIdStr = `chunk-${index}`;
        
        card.innerHTML = `
            <div class="chunk-card-meta">
                <h4>${chunk.title}</h4>
                <span class="chunk-score ${scoreClass}">Score: ${score.toFixed(4)}</span>
            </div>
            <div class="chunk-score-bar-bg">
                <div class="chunk-score-bar-fill ${scoreClass}" style="width: ${Math.min(100, score * 100)}%"></div>
            </div>
            <div class="chunk-text-toggle" onclick="toggleChunkContent('${chunkIdStr}')">View Text Chunk</div>
            <div id="${chunkIdStr}" class="chunk-raw-content hidden">${chunk.content}</div>
        `;
        container.appendChild(card);
    });
}

// Global scope injection to handle click toggling on dynamic items
window.toggleChunkContent = function(id) {
    const el = document.getElementById(id);
    if (el.classList.contains("hidden")) {
        el.classList.remove("hidden");
    } else {
        el.classList.add("hidden");
    }
};

// ==========================================
// Core Chat API Interactions
// ==========================================
async function handleSendMessage(e) {
    e.preventDefault();
    const input = document.getElementById("chat-input");
    const message = input.value.strip ? input.value.strip() : input.value.trim();
    if (!message) return;
    
    // Clear field
    input.value = "";
    
    // Append user message immediately
    appendMessage("user", message);
    
    // Trigger loader state
    const loader = document.getElementById("chat-loader");
    loader.classList.remove("hidden");
    
    // Lock submit button
    const btnSend = document.getElementById("btn-send");
    btnSend.disabled = true;
    
    try {
        const response = await fetch(`${API_BASE}/api/chat`, {
            method: "POST",
            headers: getHeaders(),
            body: JSON.stringify({
                sessionId: state.sessionId,
                message: message
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || data.detail || "API experienced an error");
        }
        
        // Hide loader
        loader.classList.add("hidden");
        btnSend.disabled = false;
        
        // Render assistant answer bubble
        appendMessage("assistant", data.reply, data.tokensUsed);
        
        // Populate RAG inspector
        updateRAGInspector(data.chunks || [], data.tokensUsed, data.retrievedChunks > 0);
        
    } catch (err) {
        loader.classList.add("hidden");
        btnSend.disabled = false;
        showToast(err.message, true);
        appendMessage("assistant", `🚨 **Error Processing Query:** ${err.message}. Please verify backend servers are running, API keys are input in \`.env\`, or modify security tokens.`);
    }
}

async function loadSessionHistory(sessId) {
    resetInspector();
    const chatContainer = document.getElementById("chat-messages");
    chatContainer.innerHTML = `
        <div class="welcome-card">
            <h2>Syncing messages...</h2>
            <p>Retrieving session records from local database stores.</p>
        </div>
    `;
    
    try {
        const response = await fetch(`${API_BASE}/api/chat/history/${sessId}`, {
            headers: getHeaders()
        });
        
        if (!response.ok) {
            throw new Error("Unable to sync histories");
        }
        
        const history = await response.json();
        chatContainer.innerHTML = "";
        
        if (history.length === 0) {
            // Restore default welcome
            chatContainer.innerHTML = `
                <div class="welcome-card">
                    <span class="welcome-icon">⚡</span>
                    <h2>How can I assist you today?</h2>
                    <p>I am a production-grade RAG assistant grounded directly in your document database. Ask me anything about TRUEAILAB's security protocols, developer guidelines, expense processes, or leave rules.</p>
                    <div class="sample-queries">
                        <button class="sample-query-btn">How can I reset my password?</button>
                        <button class="sample-query-btn">What is the home office budget for remote work?</button>
                        <button class="sample-query-btn">What is the PR code review guidelines?</button>
                    </div>
                </div>
            `;
            return;
        }
        
        history.forEach((msg) => {
            appendMessage(msg.role, msg.content, msg.tokensUsed);
        });
    } catch (err) {
        showToast("Error restoring history logs from server.", true);
        clearScreen();
    }
}

function startNewChat() {
    state.sessionId = generateId();
    if (!state.sessions.includes(state.sessionId)) {
        state.sessions.push(state.sessionId);
    }
    saveState();
    renderSessionList();
    document.getElementById("active-session-title").innerText = `Session: ${state.sessionId}`;
    clearScreen();
    showToast("Started fresh chat session!");
}

// ==========================================
// JWT Auth API Interactions (Bonus)
// ==========================================
async function handleLogin(e) {
    e.preventDefault();
    const userField = document.getElementById("auth-username");
    const passField = document.getElementById("auth-password");
    
    const username = userField.value.trim();
    const password = passField.value;
    
    if (!username || !password) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || "Authentication failed");
        }
        
        state.token = data.accessToken;
        state.username = data.username;
        saveState();
        syncAuthUI();
        showToast(`Successfully logged in as ${state.username}!`);
        
        // Reload active history to merge logged user histories
        loadSessionHistory(state.sessionId);
    } catch (err) {
        showToast(err.message, true);
    }
}

async function handleRegister() {
    const userField = document.getElementById("auth-username");
    const passField = document.getElementById("auth-password");
    
    const username = userField.value.trim();
    const password = passField.value;
    
    if (!username || !password) {
        showToast("Username and password are required.", true);
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/auth/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || "Registration failed");
        }
        
        showToast("Registration successful! Logging you in...");
        
        // Auto Login
        const loginRes = await fetch(`${API_BASE}/api/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
        });
        const loginData = await loginRes.json();
        
        if (loginRes.ok) {
            state.token = loginData.accessToken;
            state.username = loginData.username;
            saveState();
            syncAuthUI();
            loadSessionHistory(state.sessionId);
        }
    } catch (err) {
        showToast(err.message, true);
    }
}

function handleLogout() {
    state.token = null;
    state.username = null;
    saveState();
    syncAuthUI();
    showToast("Successfully logged out.");
    loadSessionHistory(state.sessionId);
}

// ==========================================
// Corpus List Inspection
// ==========================================
async function fetchCorpus() {
    try {
        const response = await fetch(`${API_BASE}/api/documents`);
        if (!response.ok) return;
        const docs = await response.json();
        
        const list = document.getElementById("inspector-kb-list");
        list.innerHTML = "";
        
        if (docs.length === 0) {
            list.innerHTML = `<div class="empty-state-chunks">No corpus loaded. Seed DB by reloading backend.</div>`;
            return;
        }
        
        docs.forEach((doc) => {
            const item = document.createElement("div");
            item.className = "kb-item";
            item.innerHTML = `
                <span class="kb-item-title" title="${doc.title}">📄 ${doc.title}</span>
                <span class="kb-item-size">${(doc.lengthBytes / 1024).toFixed(1)} KB</span>
            `;
            list.appendChild(item);
        });
    } catch (ex) {
        console.error("Unable to load corpus list:", ex);
    }
}

// ==========================================
// Toast Utility Notifications
// ==========================================
function showToast(message, isError = false) {
    const toast = document.getElementById("toast");
    toast.innerText = message;
    
    if (isError) {
        toast.style.background = "linear-gradient(135deg, #ef4444, #b91c1c)";
    } else {
        toast.style.background = "linear-gradient(135deg, #8b5cf6, #6366f1)";
    }
    
    toast.classList.remove("hidden");
    setTimeout(() => {
        toast.classList.add("show");
    }, 50);
    
    setTimeout(() => {
        toast.classList.remove("show");
        setTimeout(() => {
            toast.classList.add("hidden");
        }, 300);
    }, 4000);
}
