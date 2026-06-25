// Gamified Piano Learning - Interactive Features

(function() {
  const finishButton = document.getElementById('finishLevelBtn');
  const feedbackDiv = document.getElementById('feedbackMsg');
  let levelCompleted = false;

  // Create confetti effect
  function createConfetti() {
    const confettiContainer = document.createElement('div');
    confettiContainer.style.position = 'fixed';
    confettiContainer.style.top = '0';
    confettiContainer.style.left = '0';
    confettiContainer.style.width = '100%';
    confettiContainer.style.height = '100%';
    confettiContainer.style.pointerEvents = 'none';
    confettiContainer.style.zIndex = '9999';
    document.body.appendChild(confettiContainer);

    const colors = ['#FFD966', '#FFB347', '#FF8C42', '#F4A261', '#E9C46A', '#2A9D8F'];
    
    for (let i = 0; i < 120; i++) {
      const conf = document.createElement('div');
      conf.style.position = 'absolute';
      conf.style.width = Math.random() * 8 + 5 + 'px';
      conf.style.height = Math.random() * 8 + 5 + 'px';
      conf.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
      conf.style.borderRadius = Math.random() > 0.5 ? '50%' : '2px';
      conf.style.top = Math.random() * window.innerHeight + 'px';
      conf.style.left = Math.random() * window.innerWidth + 'px';
      conf.style.opacity = '0.9';
      conf.style.transform = `rotate(${Math.random() * 360}deg)`;
      conf.style.animation = `confettiFall ${Math.random() * 1.5 + 1.2}s linear forwards`;
      confettiContainer.appendChild(conf);
    }

    setTimeout(() => {
      confettiContainer.remove();
    }, 1800);
  }

  // Play completion sound
  function playLevelCompleteSound() {
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const oscillator = audioCtx.createOscillator();
      const gainNode = audioCtx.createGain();
      oscillator.connect(gainNode);
      gainNode.connect(audioCtx.destination);
      oscillator.frequency.value = 880;
      gainNode.gain.value = 0.2;
      oscillator.type = 'sine';
      oscillator.start();
      gainNode.gain.exponentialRampToValueAtTime(0.00001, audioCtx.currentTime + 0.8);
      oscillator.stop(audioCtx.currentTime + 0.7);
      
      if (audioCtx.state === 'suspended') {
        audioCtx.resume();
      }
    } catch(e) {
      console.log("Web Audio not supported");
    }
  }

  // Show feedback message
  function showRewardMessage(message, isError = false) {
    if (isError) {
      feedbackDiv.style.color = '#c2441b';
      feedbackDiv.style.fontWeight = 'bold';
    } else {
      feedbackDiv.style.color = '#2c6e2f';
      feedbackDiv.style.fontWeight = '600';
    }
    feedbackDiv.innerHTML = message;
    
    setTimeout(() => {
      if (!levelCompleted) {
        feedbackDiv.innerHTML = '';
      }
    }, 2500);
  }

  // Main finish level action
  function finishLevelAction() {
    if (levelCompleted) {
      showRewardMessage("🎉 Level already mastered! Try the next lesson soon! 🎉", false);
      return;
    }
    
    levelCompleted = true;
    
    // Update XP
    const xpSpan = document.querySelector('.xp-points');
    if (xpSpan) {
      let currentXP = parseInt(xpSpan.innerText.match(/\d+/)?.[0] || 2450);
      const newXP = currentXP + 350;
      xpSpan.innerHTML = `🎯 ${newXP} XP`;
      
      const plusBadge = document.createElement('span');
      plusBadge.innerText = '+350 XP!';
      plusBadge.style.position = 'relative';
      plusBadge.style.left = '10px';
      plusBadge.style.fontWeight = 'bold';
      plusBadge.style.color = '#ffd966';
      plusBadge.style.fontSize = '0.8rem';
      plusBadge.style.animation = 'fadeOutUp 1s forwards';
      xpSpan.appendChild(plusBadge);
      
      setTimeout(() => {
        if (plusBadge) plusBadge.remove();
      }, 1000);
    }
    
    // Trigger effects
    createConfetti();
    playLevelCompleteSound();
    
    // Update level text
    const levelSpan = document.querySelector('.level-text');
    if (levelSpan && !levelSpan.innerText.includes('MASTER')) {
      levelSpan.innerHTML = '🏅 LEVEL 4 · NOTE WIZARD 🏅';
    } else if (levelSpan) {
      levelSpan.innerHTML = '🏅 LEVEL MASTER · PIANO LEGEND 🏅';
    }
    
    showRewardMessage("✨✨ AMAZING! LEVEL COMPLETE! You've mastered Treble & Bass Clef! ✨✨ +350 XP", false);
    
    // Update button style
    finishButton.style.background = "#8fbc8f";
    finishButton.style.boxShadow = "0 4px 0 #4a6e3b";
    finishButton.innerHTML = "🏁 LEVEL MASTERED 🏁";
    
    // Animate all note bubbles
    const noteElements = document.querySelectorAll('.note-bubble');
    noteElements.forEach((note, idx) => {
      setTimeout(() => {
        note.style.transform = 'scale(1.08)';
        setTimeout(() => { note.style.transform = ''; }, 200);
      }, idx * 30);
    });
  }
  
  // Add hover effect to mnemonics
  const mnemonics = document.querySelectorAll('.mnemonic');
  mnemonics.forEach(m => {
    m.addEventListener('mouseenter', () => {
      m.style.backgroundColor = '#ffe6c7';
    });
    m.addEventListener('mouseleave', () => {
      m.style.backgroundColor = '#ffffffba';
    });
  });
  
  // Attach event listener
  finishButton.addEventListener('click', finishLevelAction);
  
  // Initial welcome message
  setTimeout(() => {
    feedbackDiv.innerHTML = "🎵 Tap any note to review! Click FINISH LEVEL to claim reward! 🎵";
    setTimeout(() => {
      if (!levelCompleted) feedbackDiv.innerHTML = "";
    }, 3000);
  }, 500);
})();