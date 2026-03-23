/* ============================================================
   main.js — 뷰티 진단 프론트엔드
   ============================================================ */
document.addEventListener("DOMContentLoaded", () => {
  // ── DOM 참조 ──
  const $upload      = document.getElementById("upload-section");
  const $loading     = document.getElementById("loading-section");
  const $result      = document.getElementById("result-section");
  const $uploadArea  = document.getElementById("upload-area");
  const $fileInput   = document.getElementById("file-input");
  const $previewArea = document.getElementById("preview-area");
  const $previewImg  = document.getElementById("preview-img");
  const $btnCamera   = document.getElementById("btn-camera");
  const $btnAnalyze  = document.getElementById("btn-analyze");
  const $btnChange   = document.getElementById("btn-change");
  const $btnRetry    = document.getElementById("btn-retry");
  const $loadingStep = document.getElementById("loading-step");
  const $loadingBar  = document.getElementById("loading-bar");

  // ── 웹캠 모달 DOM ──
  const $cameraModal   = document.getElementById("camera-modal");
  const $cameraClose   = document.getElementById("camera-close");
  const $cameraVideo   = document.getElementById("camera-video");
  const $cameraCapture = document.getElementById("camera-capture");
  const $cameraSwitch  = document.getElementById("camera-switch");
  const $cameraCanvas  = document.getElementById("camera-canvas");

  let selectedFile = null;
  let cameraStream = null;
  let useFrontCamera = true;

  // ============================================================
  //  섹션 전환
  // ============================================================
  function showSection(section) {
    [$upload, $loading, $result].forEach(s => s.classList.remove("active"));
    section.classList.add("active");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // ============================================================
  //  파일 선택 & 미리보기
  // ============================================================
  function handleFile(file, autoAnalyze = false) {
    if (!file) return;
    const allowed = ["image/png", "image/jpeg", "image/jpg", "image/webp"];
    if (!allowed.includes(file.type)) {
      alert("지원하지 않는 파일 형식입니다.\nPNG, JPG, JPEG, WebP 만 가능합니다.");
      return;
    }
    if (file.size > 16 * 1024 * 1024) {
      alert("파일 크기가 16MB를 초과합니다.");
      return;
    }

    selectedFile = file;
    const reader = new FileReader();
    reader.onload = (e) => {
      $previewImg.src = e.target.result;
      $uploadArea.classList.add("hidden");
      $previewArea.classList.remove("hidden");
      $btnAnalyze.disabled = false;

      // 카메라 촬영 시 바로 분석 시작
      if (autoAnalyze) {
        $btnAnalyze.click();
      }
    };
    reader.readAsDataURL(file);
  }

  // 클릭 → 파일 선택
  $uploadArea.addEventListener("click", () => $fileInput.click());
  $fileInput.addEventListener("change", (e) => handleFile(e.target.files[0]));

  // 드래그 & 드롭
  $uploadArea.addEventListener("dragover", (e) => {
    e.preventDefault();
    $uploadArea.classList.add("drag-over");
  });
  $uploadArea.addEventListener("dragleave", () => {
    $uploadArea.classList.remove("drag-over");
  });
  $uploadArea.addEventListener("drop", (e) => {
    e.preventDefault();
    $uploadArea.classList.remove("drag-over");
    handleFile(e.dataTransfer.files[0]);
  });

  // ============================================================
  //  웹캠 카메라 모달
  // ============================================================
  async function openCamera() {
    try {
      stopCamera();
      const constraints = {
        video: {
          facingMode: useFrontCamera ? "user" : "environment",
          width: { ideal: 1280 },
          height: { ideal: 960 },
        },
        audio: false,
      };
      cameraStream = await navigator.mediaDevices.getUserMedia(constraints);
      $cameraVideo.srcObject = cameraStream;
      $cameraModal.classList.remove("hidden");
    } catch (err) {
      console.error("카메라 접근 실패:", err);
      alert("카메라를 열 수 없습니다: " + err.message);
    }
  }

  function stopCamera() {
    if (cameraStream) {
      cameraStream.getTracks().forEach(track => track.stop());
      cameraStream = null;
    }
    $cameraVideo.srcObject = null;
  }

  function closeCamera() {
    stopCamera();
    $cameraModal.classList.add("hidden");
  }

  $btnCamera.addEventListener("click", () => openCamera());
  $cameraClose.addEventListener("click", () => closeCamera());
  document.querySelector(".camera-overlay").addEventListener("click", () => closeCamera());
  $cameraSwitch.addEventListener("click", () => {
    useFrontCamera = !useFrontCamera;
    openCamera();
  });

  $cameraCapture.addEventListener("click", () => {
    if (!cameraStream) return;
    const video = $cameraVideo;
    const canvas = $cameraCanvas;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (useFrontCamera) {
      ctx.translate(canvas.width, 0);
      ctx.scale(-1, 1);
    }
    ctx.drawImage(video, 0, 0);
    canvas.toBlob((blob) => {
      if (!blob) return;
      const capturedFile = new File([blob], "camera_capture.jpg", { type: "image/jpeg" });
      closeCamera();
      handleFile(capturedFile, true);
    }, "image/jpeg", 0.92);
  });

  $btnChange.addEventListener("click", () => {
    selectedFile = null;
    $fileInput.value = "";
    $previewArea.classList.add("hidden");
    $uploadArea.classList.remove("hidden");
    $btnAnalyze.disabled = true;
  });

  $btnRetry.addEventListener("click", () => {
    selectedFile = null;
    $fileInput.value = "";
    $previewArea.classList.add("hidden");
    $uploadArea.classList.remove("hidden");
    $btnAnalyze.disabled = true;
    showSection($upload);
  });

  // ============================================================
  //  분석 요청
  // ============================================================
  $btnAnalyze.addEventListener("click", async () => {
    if (!selectedFile) return;
    showSection($loading);
    const steps = [
      { text: "이미지를 처리하고 있습니다...", pct: 20 },
      { text: "퍼스널컬러를 판별하고 있습니다...", pct: 45 },
      { text: "피부 상태를 분석하고 있습니다...", pct: 70 },
      { text: "결과를 정리하고 있습니다...", pct: 90 },
    ];
    let stepIdx = 0;
    const stepTimer = setInterval(() => {
      if (stepIdx < steps.length) {
        $loadingStep.textContent = steps[stepIdx].text;
        $loadingBar.style.width = steps[stepIdx].pct + "%";
        stepIdx++;
      }
    }, 700);

    try {
      const formData = new FormData();
      formData.append("image", selectedFile);
      const resp = await fetch("/api/diagnosis", { // 기존에 작동하던 안정적인 경로로 복구
        method: "POST",
        body: formData,
      });
      const data = await resp.json();
      clearInterval(stepTimer);
      $loadingBar.style.width = "100%";
      if (!data.success) {
        alert(data.error || "분석에 실패했습니다.");
        showSection($upload);
        return;
      }
      await new Promise((r) => setTimeout(r, 500));
      renderResults(data);
      showSection($result);
    } catch (err) {
      clearInterval(stepTimer);
      console.error(err);
      alert("서버 연결에 실패했습니다.");
      showSection($upload);
    }
  });

  // ============================================================
  //  상품 클릭 로그 기록 (Backend Leader 전용 기능)
  // ============================================================
  window.handleProductClick = async function(event, name, link) {
    // 1. 서버에 로그 전송
    try {
      await fetch("/api/click-log", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ product_name: name, product_link: link })
      });
    } catch (e) {
      console.error("클릭 로그 전송 실패:", e);
    }
    // 2. 실제 링크로 이동 (target="_blank" 속성이 있다면 브라우저가 새 탭을 엽니다)
  };

  // ============================================================
  //  결과 렌더링 (서버 응답 키값 동기화 완료)
  // ============================================================
  function renderResults(data) {
    // 서버(diagnosis.py)에서 보내주는 정확한 키값으로 매핑
    const pc = data.personal_color;
    const sk = data.skin_analysis;

    // ── 1. 퍼스널컬러 영역 ──
    if (pc && pc.success) {
      document.getElementById("color-emoji").textContent = pc.emoji || "✨";
      document.getElementById("color-season").textContent = pc.season;
      document.getElementById("color-subtitle").textContent = pc.subtitle;
      document.getElementById("color-description").textContent = data.ai_advice || "분석 결과를 토대로 상담을 받아보세요.";
      
      const $reasoning = document.getElementById("reasoning-list");
      $reasoning.innerHTML = (pc.reasoning || []).map(r => `
        <div class="reasoning-item">
          <span class="reasoning-factor">${r.factor}</span>
          <div class="reasoning-body">
            <span class="reasoning-value">${r.value}</span>
            <span class="reasoning-detail">${r.detail}</span>
          </div>
        </div>
      `).join("");

      document.getElementById("palette-best").innerHTML = (pc.best_colors || []).map((name, i) => `
        <div class="swatch">
          <div class="swatch-circle" style="background:${pc.color_codes ? pc.color_codes[i] : '#ccc'}"></div>
          <span class="swatch-label">${name}</span>
        </div>
      `).join("");

      document.getElementById("palette-worst").innerHTML = (pc.worst_colors || []).map((name, i) => `
        <div class="swatch">
          <div class="swatch-circle" style="background:${pc.worst_color_codes ? pc.worst_color_codes[i] : '#888'}"></div>
          <span class="swatch-label">${name}</span>
        </div>
      `).join("");
    }

    // ── 2. 피부 분석 영역 ──
    if (sk && sk.success) {
      const score = sk.overall_score || 0;
      document.getElementById("score-number").textContent = score;
      const arc = document.getElementById("score-arc");
      const offset = 314 - (314 * score) / 100;
      requestAnimationFrame(() => { arc.style.strokeDashoffset = offset; });

      const st = sk.skin_type || {};
      document.getElementById("skin-emoji").textContent = st.emoji || "👤";
      document.getElementById("skin-type-name").textContent = st.name || "분석 완료";
      document.getElementById("skin-type-desc").textContent = st.description || "";

      const $metrics = document.getElementById("metrics-grid");
      const condKeys = ["brightness", "evenness", "redness", "texture", "moisture", "oiliness"];
      $metrics.innerHTML = condKeys.map(key => {
        const c = sk.conditions ? sk.conditions[key] : null;
        if (!c) return "";
        return `
          <div class="metric-item status-${c.status}">
            <label><span>${c.label}</span><span class="metric-score">${c.score}점</span></label>
            <div class="metric-bar"><div class="metric-bar-fill" style="width: 0%" data-width="${c.score}"></div></div>
            <div class="metric-detail">${c.detail}</div>
          </div>
        `;
      }).join("");

      setTimeout(() => {
        document.querySelectorAll(".metric-bar-fill").forEach(el => {
          el.style.width = el.dataset.width + "%";
        });
      }, 100);
    }

    // ── 3. 쇼핑 추천 영역 ──
    renderProducts(data.color_products, "color-products", "color-products-empty");
    renderProducts(data.skin_products, "skin-products", "skin-products-empty");
  }

  function renderProducts(products, gridId, emptyId) {
    const $grid = document.getElementById(gridId);
    const $empty = document.getElementById(emptyId);
    if (!$grid) return;
    if (!products || products.length === 0) {
      $grid.innerHTML = "";
      if ($empty) $empty.classList.remove("hidden");
      return;
    }
    if ($empty) $empty.classList.add("hidden");

    $grid.innerHTML = products.map(p => `
      <a class="product-card" href="${p.link}" target="_blank" rel="noopener" 
         onclick="handleProductClick(event, '${p.title.replace(/'/g, "\\'")}', '${p.link}')">
        <img class="product-card-img" src="${p.image}" alt="${p.title}" />
        <div class="product-card-body">
          <div class="product-title">${p.title}</div>
          <div class="product-price">₩${Number(p.price).toLocaleString()}</div>
        </div>
      </a>
    `).join("");
  }

  // ============================================================
  // 제미나이 AI 챗봇 로직
  // ============================================================
  const $btnOpenChat = document.getElementById("btn-open-chat");
  const $chatModal   = document.getElementById("chat-modal");
  const $chatClose   = document.getElementById("chat-close");
  const $chatOverlay = document.getElementById("chat-overlay");
  const $chatMessages = document.getElementById("chat-messages");
  const $chatInput   = document.getElementById("chat-input");
  const $btnSendChat = document.getElementById("btn-send-chat");

  let chatHistory = [];

  function openChatModal() {
    $chatModal.classList.remove("hidden");
    if ($chatMessages.innerHTML.trim() === "") {
        appendChatMessage("ai", "반갑습니다! 당신의 뷰티 고민을 해결해드릴 AI 컨설턴트 벨라입니다. 피부 타입이나 스킨케어, 어울리는 스타일까지 무엇이든 편하게 물어보세요! ✨");
    }
  }
  function closeChatModal() {
    $chatModal.classList.add("hidden");
  }

  $btnOpenChat?.addEventListener("click", openChatModal);
  $chatClose?.addEventListener("click", closeChatModal);
  $chatOverlay?.addEventListener("click", closeChatModal);

  function appendChatMessage(type, text) {
    const msgDiv = document.createElement("div");
    msgDiv.className = `chat-msg chat-${type}`;
    msgDiv.innerHTML = type === 'ai' ? 
        `<strong>벨라 💄</strong><p>${text.replace(/\\n/g, '<br>')}</p>` : 
        `<strong>나</strong><p>${text.replace(/\\n/g, '<br>')}</p>`;
    $chatMessages.appendChild(msgDiv);
    $chatMessages.scrollTop = $chatMessages.scrollHeight;
  }

  async function sendChatMessage() {
    const message = $chatInput.value.trim();
    if (!message) return;

    $chatInput.value = "";
    appendChatMessage("user", message);
    $btnSendChat.disabled = true;

    // 현재 진단 정보 가져오기
    const colorSeason = document.getElementById("color-season")?.textContent || "모름";
    const skinType = document.getElementById("skin-type-name")?.textContent || "모름";
    const skinScore = document.getElementById("score-number")?.textContent || "0";
    const contextText = `사용자의 진단 결과 - 퍼스널컬러: ${colorSeason}, 피부타입: ${skinType} (${skinScore}점)`;

    try {
      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: message,
          context: contextText,
          history: chatHistory
        })
      });
      const data = await resp.json();

      if (data.success) {
        appendChatMessage("ai", data.response);
        chatHistory.push({ role: "user", text: message });
        chatHistory.push({ role: "model", text: data.response });
      } else {
        appendChatMessage("ai", `오류가 발생했습니다: ${data.error}`);
      }
    } catch (err) {
      console.error(err);
      appendChatMessage("ai", "서버 연결에 실패했습니다.");
    } finally {
      $btnSendChat.disabled = false;
      $chatInput.focus();
    }
  }

  $btnSendChat?.addEventListener("click", sendChatMessage);
  $chatInput?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendChatMessage();
  });
});
