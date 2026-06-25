let audioCtx = null;

function getAudioCtx() {
    if (!audioCtx) {
        const AudioClass = window.AudioContext || window.webkitAudioContext;
        if (!AudioClass) return null;
        audioCtx = new AudioClass();
    }

    if (audioCtx.state === "suspended") {
        audioCtx.resume();
    }

    return audioCtx;
}

const frequencies = {
    "C": 261.63,
    "C#": 277.18,
    "D": 293.66,
    "D#": 311.13,
    "E": 329.63,
    "F": 349.23,
    "F#": 369.99,
    "G": 392.00,
    "G#": 415.30,
    "A": 440.00,
    "A#": 466.16,
    "B": 493.88,
    "C2": 523.25
};

const pianoLayout = [
    { note: "C", color: "white", label: "C", keyChar: "A" },
    { note: "C#", color: "black", label: "C#", after: 1, keyChar: "W" },
    { note: "D", color: "white", label: "D", keyChar: "S" },
    { note: "D#", color: "black", label: "D#", after: 2, keyChar: "E" },
    { note: "E", color: "white", label: "E", keyChar: "D" },
    { note: "F", color: "white", label: "F", keyChar: "F" },
    { note: "F#", color: "black", label: "F#", after: 4, keyChar: "T" },
    { note: "G", color: "white", label: "G", keyChar: "G" },
    { note: "G#", color: "black", label: "G#", after: 5, keyChar: "Y" },
    { note: "A", color: "white", label: "A", keyChar: "H" },
    { note: "A#", color: "black", label: "A#", after: 6, keyChar: "U" },
    { note: "B", color: "white", label: "B", keyChar: "J" },
    { note: "C2", color: "white", label: "C", keyChar: "K" }
];

const trebleStaffPos = {
    "C": 138,
    "C#": 138,
    "D": 130,
    "D#": 130,
    "E": 122,
    "F": 114,
    "F#": 114,
    "G": 106,
    "G#": 106,
    "A": 98,
    "A#": 98,
    "B": 90,
    "C2": 82
};

const bassStaffPos = {
    "C": 100,
    "D": 92,
    "E": 84,
    "F": 76,
    "G": 68
};

const trebleQuestionNotes = Object.keys(trebleStaffPos);
const bassQuestionNotes = Object.keys(bassStaffPos);

let currentNote = "";
let currentClef = "treble";
let score = 0;
let combo = 0;
let lives = 5;

const maxLives = 5;
const maxScore = 15;
const trebleQuestionCount = 10;

function playNote(note) {
    const ctx = getAudioCtx();
    if (!ctx || !frequencies[note]) return;

    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = "triangle";
    osc.frequency.setValueAtTime(frequencies[note], now);

    gain.gain.setValueAtTime(0.26, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.72);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(now);
    osc.stop(now + 0.72);
}

function playTone(freq, type = "sine") {
    const ctx = getAudioCtx();
    if (!ctx) return;

    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = type;
    osc.frequency.setValueAtTime(freq, now);

    gain.gain.setValueAtTime(0.18, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.24);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(now);
    osc.stop(now + 0.24);
}

function renderHearts() {
    return Array.from({ length: maxLives }, (_, index) => {
        return `<span class="heart${index >= lives ? " lost" : ""}">${index < lives ? "♥" : "♡"}</span>`;
    }).join("");
}

function updateStats() {
    const percent = Math.min(100, Math.round((score / maxScore) * 100));

    document.getElementById("scoreValue").textContent = score;
    document.getElementById("comboValue").textContent = combo;
    document.getElementById("comboText").textContent = combo >= 5 ? "Perfect!" : "Keep going!";
    document.getElementById("livesValue").innerHTML = renderHearts();
    document.getElementById("progressFill").style.width = percent + "%";
    document.getElementById("progressText").textContent = percent + "%";
}

function setFeedback(text, type) {
    const feedback = document.getElementById("instruction");
    feedback.textContent = text;
    feedback.className = "feedback-line";

    if (type) {
        feedback.classList.add(type);
    }
}

function drawStaff(note, clef = "treble") {
    const canvas = document.getElementById("staff");
    const ctx = canvas.getContext("2d");

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    ctx.strokeStyle = "#333";
    ctx.lineWidth = 2;

    for (let i = 0; i < 5; i++) {
        const y = 60 + i * 16;

        ctx.beginPath();
        ctx.moveTo(50, y);
        ctx.lineTo(550, y);
        ctx.stroke();
    }

    ctx.font = "70px serif";
    ctx.fillStyle = "#333";
    ctx.fillText(clef === "bass" ? "\uD834\uDD22" : "\uD834\uDD1E", 60, clef === "bass" ? 116 : 130);

    const staffPositions = clef === "bass" ? bassStaffPos : trebleStaffPos;
    const y = staffPositions[note];

    if (note.includes("#")) {
        ctx.font = "26px serif";
        ctx.fillText("♯", 270, y + 9);
    }

    if (clef === "treble" && (note === "C" || note === "C#")) {
        ctx.beginPath();
        ctx.moveTo(280, 138);
        ctx.lineTo(320, 138);
        ctx.stroke();
    }

    ctx.fillStyle = "#111";
    ctx.beginPath();
    ctx.ellipse(300, y, 10, 7, -0.35, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = "#111";
    ctx.lineWidth = 2;

    ctx.beginPath();
    ctx.moveTo(309, y);
    ctx.lineTo(309, y - 45);
    ctx.stroke();
}

function newQuestion() {
    const isBassQuestion = score >= trebleQuestionCount;
    const notes = isBassQuestion ? bassQuestionNotes : trebleQuestionNotes;

    currentClef = isBassQuestion ? "bass" : "treble";
    currentNote = notes[Math.floor(Math.random() * notes.length)];

    setFeedback("Click the matching piano key");
    drawStaff(currentNote, currentClef);
}

function flashKey(note, state) {
    const key = document.querySelector(`[data-note="${note}"]`);
    if (!key) return;

    key.classList.add("active", state);

    setTimeout(() => {
        key.classList.remove("active", state);
    }, 360);
}

function handleInput(note) {
    playNote(note);

    if (note === currentNote) {
        score++;
        combo++;

        flashKey(note, "correct");
        setFeedback("Correct! That was " + currentNote, "good");
        playTone(1046.5);
        updateStats();

        if (score >= maxScore) {
            saveGameResult(score, true);
            showCompletion(true);
            return;
        }

        setTimeout(newQuestion, 600);
        return;
    }

    lives--;
    combo = 0;

    flashKey(note, "wrong");
    setFeedback("Wrong! That was " + currentNote, "bad");
    playTone(180, "sawtooth");
    updateStats();

    document.getElementById("game-container").classList.add("shake");

    setTimeout(() => {
        document.getElementById("game-container").classList.remove("shake");

        if (lives <= 0) {
            saveGameResult(score, false);
            showCompletion(false);
            return;
        }

        newQuestion();
    }, 800);
}

function renderPiano() {
    const piano = document.getElementById("piano");
    piano.innerHTML = "";

    const whiteNotes = pianoLayout.filter(item => item.color === "white");
    const blackNotes = pianoLayout.filter(item => item.color === "black");

    whiteNotes.forEach(item => {
        const key = document.createElement("button");
        key.type = "button";
        key.className = "white-key";
        key.dataset.note = item.note;
        key.innerHTML = `<span class="key-label">${item.label}</span>`;
        key.addEventListener("click", () => handleInput(item.note));
        piano.appendChild(key);
    });

    blackNotes.forEach(item => {
        const key = document.createElement("button");
        key.type = "button";
        key.className = "black-key";
        key.dataset.note = item.note;
        key.style.left = `calc((var(--white-w) * ${item.after}) - (var(--black-w) / 2))`;
        key.innerHTML = `<span class="key-label">${item.label}</span>`;
        key.addEventListener("click", () => handleInput(item.note));
        piano.appendChild(key);
    });
}

function showCompletion(won) {
    const game = document.getElementById("game-container");

    game.innerHTML = `
        <section class="completion">
            <div>
                <div class="badge" style="margin: 0 auto 22px; width: 86px; height: 86px; font-size: 2.5rem;">${won ? "★" : "♥"}</div>
                <h2>${won ? "Maestro!" : "Try Again"}</h2>
                <p style="color: var(--muted); margin-bottom: 26px;">Final score: <strong style="color: var(--gold-soft);">${score} / ${maxScore}</strong></p>
                <div class="home-actions">
                    <button class="primary-btn" onclick="restartGame()">Play Again</button>
                    <button class="primary-btn" onclick="goNextLesson()">Next Lesson</button>
                    <button class="ghost-btn" onclick="goExit()">Exit</button>
                </div>
            </div>
        </section>
    `;
}

function goNextLesson() {
    if (window.location.protocol.startsWith('http')) {
        window.location.href = '/lesson2-2';
    } else {
        window.location.href = 'level 2(lesson 2).html';
    }
}

function goExit() {
    if (window.location.protocol.startsWith('http')) {
        window.location.href = '/';
    } else {
        window.location.href = 'index.html';
    }
}

function restartGame() {
    score = 0;
    combo = 0;
    lives = maxLives;

    const game = document.getElementById("game-container");

    game.innerHTML = `
        <div class="level-ribbon">LESSON 1</div>

        <div class="challenge-header">
            <div class="challenge-title">
                <div class="mini-mark">▥</div>
                <div>
                    <h1>Pianova</h1>
                    <p>Identify the note</p>
                </div>
            </div>

            <button class="difficulty">♫ LESSON 1 ˅</button>
        </div>

        <div class="feedback-line" id="instruction">Click the matching piano key</div>

        <div class="staff-card">
            <canvas id="staff" width="600" height="180"></canvas>
        </div>

        <div class="piano-wrap">
            <div class="piano" id="piano"></div>
        </div>

        <p class="instruction">Click the piano key that matches the staff</p>
    `;

    renderPiano();
    updateStats();
    newQuestion();
}

function saveGameResult(finalScore, passed) {
    fetch("/api/save-game2", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            score: finalScore,
            total_questions: maxScore,
            passed: passed
        })
    }).catch(() => {});
}

document.getElementById("resetBtn").addEventListener("click", restartGame);
document.getElementById("soundBtn").addEventListener("click", () => playTone(880));

window.addEventListener("keydown", event => {
    const key = event.key.toUpperCase();
    const found = pianoLayout.find(item => item.keyChar === key);

    if (!found) return;

    event.preventDefault();
    handleInput(found.note);
});

const practiceSessionStartedAt = Date.now();
let practiceSessionSent = false;

function sendPracticeSession() {
    if (practiceSessionSent) return;

    practiceSessionSent = true;

    const durationSeconds = Math.max(1, Math.round((Date.now() - practiceSessionStartedAt) / 1000));
    const payload = JSON.stringify({
        game_type: "game2",
        duration_seconds: durationSeconds
    });

    if (navigator.sendBeacon) {
        navigator.sendBeacon("/api/log-practice-session", new Blob([payload], {
            type: "application/json"
        }));
        return;
    }

    fetch("/api/log-practice-session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload,
        keepalive: true
    }).catch(() => {});
}

window.addEventListener("pagehide", sendPracticeSession);
window.addEventListener("beforeunload", sendPracticeSession);

renderPiano();
updateStats();
newQuestion();
