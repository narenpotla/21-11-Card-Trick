/*
 * Interaction polish only -- no game state or card-position logic here.
 * The server (cardtrick/views.py + cardtrick/logic.py) is the sole
 * source of truth for what card is where; this file just makes the
 * page feel alive, and delays the real form submission just long
 * enough for the "chosen pile glows, others fade" animation to play.
 */

const CONFETTI_COUNT = 90;
const CONFETTI_COLORS_HUE_RANGE = 360;
const SELECT_ANIMATION_MS = 550;

/* ---- tiny self-contained sound cues (no audio files) ---- */
let audioCtx = null;

function getAudioContext() {
  if (!audioCtx) {
    const Ctor = window.AudioContext || window.webkitAudioContext;
    if (!Ctor) return null;
    audioCtx = new Ctor();
  }
  return audioCtx;
}

function playTone(freq, duration, type, peakGain) {
  try {
    const ctx = getAudioContext();
    if (!ctx) return;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = type;
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0, ctx.currentTime);
    gain.gain.linearRampToValueAtTime(peakGain, ctx.currentTime + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + duration);
    osc.connect(gain).connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + duration + 0.02);
  } catch (err) {
    /* Web Audio unavailable or blocked -- fail silently, sound is decoration only */
  }
}

function playChipSound() {
  playTone(720, 0.09, "triangle", 0.05);
}

function playDealSound() {
  playTone(320, 0.05, "square", 0.018);
}

function playWinSound() {
  playTone(660, 0.15, "sine", 0.05);
  setTimeout(() => playTone(880, 0.18, "sine", 0.05), 110);
  setTimeout(() => playTone(1108, 0.28, "sine", 0.06), 230);
}

/* ---- confetti for the reveal moment ---- */
function spawnConfetti() {
  for (let i = 0; i < CONFETTI_COUNT; i++) {
    const piece = document.createElement("div");
    piece.className = "confetti";
    piece.style.left = `${Math.random() * 100}%`;
    piece.style.backgroundColor = `hsl(${Math.random() * CONFETTI_COLORS_HUE_RANGE}, 100%, 50%)`;

    const fallSpeed = Math.random() * 2 + 3;
    let rotation = Math.random() * 360;
    let top = -10;

    document.body.appendChild(piece);

    const step = () => {
      top += fallSpeed;
      rotation += 4;
      piece.style.transform = `translateY(${top}px) rotate(${rotation}deg)`;
      if (top < window.innerHeight + 20) {
        requestAnimationFrame(step);
      } else {
        piece.remove();
      }
    };
    requestAnimationFrame(step);
  }
}

/* ---- pile selection: animate, then actually submit ---- */
let isSubmitting = false;

function selectPileAndSubmit(columnIndex) {
  if (isSubmitting) return;
  const form = document.querySelector(".choice-form");
  if (!form) return;
  const button = form.querySelector(`button[value="${columnIndex}"]`);
  if (!button) return;

  isSubmitting = true;
  playChipSound();

  document.querySelectorAll(".column[data-column]").forEach((col) => {
    if (col.dataset.column === String(columnIndex)) {
      col.classList.add("is-selected");
    } else {
      col.classList.add("is-fading");
    }
  });

  button.classList.add("is-pressed");
  const ring = document.createElement("span");
  ring.className = "chip__ring is-active";
  button.appendChild(ring);

  // The server, not this timer, is the source of truth for the round --
  // this delay only lets the CSS animation play before the real POST.
  let hiddenColumn = form.querySelector('input[name="column"]');
  if (!hiddenColumn) {
    hiddenColumn = document.createElement("input");
    hiddenColumn.type = "hidden";
    hiddenColumn.name = "column";
    form.appendChild(hiddenColumn);
  }
  hiddenColumn.value = String(columnIndex);

  setTimeout(() => form.submit(), SELECT_ANIMATION_MS);
}

function wireChipClicks() {
  document.querySelectorAll(".chip[name=\"column\"]").forEach((chip) => {
    chip.addEventListener("click", (event) => {
      event.preventDefault();
      selectPileAndSubmit(chip.value);
    });
  });
}

// Let a click anywhere on a pile trigger the same selection -- easier to
// hit on a phone than the small chip underneath.
function wireBoardPileClicks() {
  document.querySelectorAll(".column[data-column]").forEach((column) => {
    column.addEventListener("click", () => {
      selectPileAndSubmit(column.dataset.column);
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  if (document.querySelector(".board")) {
    playDealSound();
  }

  const revealedCard = document.getElementById("revealed-card");
  if (revealedCard) {
    spawnConfetti();
    playWinSound();
  }

  wireChipClicks();
  wireBoardPileClicks();
});
