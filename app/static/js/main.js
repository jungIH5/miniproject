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
      // 이전 스트림 정리
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
      if (err.name === "NotAllowedError") {
        alert("카메라 접근 권한이 거부되었습니다.\n브라우저 설정에서 카메라 권한을 허용해주세요.");
      } else if (err.name === "NotFoundError") {
        alert("연결된 카메라를 찾을 수 없습니다.\n웹캠이 올바르게 연결되어 있는지 확인해주세요.");
      } else {
        alert("카메라를 열 수 없습니다: " + err.message);
      }
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

  // 카메라 열기
  $btnCamera.addEventListener("click", () => openCamera());

  // 카메라 닫기
  $cameraClose.addEventListener("click", () => closeCamera());
  document.querySelector(".camera-overlay").addEventListener("click", () => closeCamera());

  // 카메라 전환 (전면 ↔ 후면)
  $cameraSwitch.addEventListener("click", () => {
    useFrontCamera = !useFrontCamera;
    openCamera();
  });

  // 촬영 (캡처)
  $cameraCapture.addEventListener("click", () => {
    if (!cameraStream) return;

    const video = $cameraVideo;
    const canvas = $cameraCanvas;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext("2d");
    // 거울 모드 반영 (전면 카메라)
    if (useFrontCamera) {
      ctx.translate(canvas.width, 0);
      ctx.scale(-1, 1);
    }
    ctx.drawImage(video, 0, 0);

    // Canvas → Blob → File
    canvas.toBlob((blob) => {
      if (!blob) return;
      const capturedFile = new File([blob], "camera_capture.jpg", { type: "image/jpeg" });
      closeCamera();
      handleFile(capturedFile, true);  // 촬영 후 바로 분석 시작
    }, "image/jpeg", 0.92);
  });

  // ESC 키로 카메라 모달 닫기
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$cameraModal.classList.contains("hidden")) {
      closeCamera();
    }
  });

  // 다른 사진 선택
  $btnChange.addEventListener("click", () => {
    selectedFile = null;
    $fileInput.value = "";
    $previewArea.classList.add("hidden");
    $uploadArea.classList.remove("hidden");
    $btnAnalyze.disabled = true;
  });

  // 다시 진단하기
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

    // 로딩 애니메이션
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

      const resp = await fetch("/api/diagnosis", {
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

      // 잠시 대기 후 결과 표시
      await new Promise((r) => setTimeout(r, 500));
      renderResults(data);
      showSection($result);

    } catch (err) {
      clearInterval(stepTimer);
      console.error(err);
      alert("서버 연결에 실패했습니다. 잠시 후 다시 시도해주세요.");
      showSection($upload);
    }
  });

  // ============================================================
  //  결과 렌더링
  // ============================================================
  function renderResults(data) {
    const pc = data.personal_color;
    const sk = data.skin_analysis;

    // ── 퍼스널컬러 ──
    if (pc && pc.success) {
      document.getElementById("color-emoji").textContent = pc.emoji;
      document.getElementById("color-season").textContent = pc.season;
      document.getElementById("color-subtitle").textContent = pc.subtitle;
      document.getElementById("color-description").textContent = pc.description;

      // 분석 근거
      const $reasoning = document.getElementById("reasoning-list");
      $reasoning.innerHTML = pc.reasoning.map(r => `
        <div class="reasoning-item">
          <span class="reasoning-factor">${r.factor}</span>
          <div class="reasoning-body">
            <span class="reasoning-value">${r.value}</span>
            <span class="reasoning-detail">${r.detail}</span>
          </div>
        </div>
      `).join("");

      // 추천 팔레트
      const $best = document.getElementById("palette-best");
      $best.innerHTML = pc.best_colors.map((name, i) => `
        <div class="swatch">
          <div class="swatch-circle" style="background:${pc.color_codes[i] || '#ccc'}"></div>
          <span class="swatch-label">${name}</span>
        </div>
      `).join("");

      // 비추천 팔레트 (실제 색상 + X 표시)
      const $worst = document.getElementById("palette-worst");
      $worst.innerHTML = pc.worst_colors.map((name, i) => `
        <div class="swatch">
          <div class="swatch-circle" style="background:${(pc.worst_color_codes && pc.worst_color_codes[i]) || '#888'}"></div>
          <span class="swatch-label">${name}</span>
        </div>
      `).join("");
    }

    // ── 퍼스널컬러 맞춤 제품 ──
    renderProducts(data.color_products, "color-products", "color-products-empty");

    // ── 피부 분석 ──
    if (sk && sk.success) {
      // SVG 그래디언트 (동적 삽입)
      ensureScoreGradient();

      // 전체 점수 원형 게이지
      const score = sk.overall_score;
      document.getElementById("score-number").textContent = score;
      const arc = document.getElementById("score-arc");
      const offset = 314 - (314 * score) / 100;
      requestAnimationFrame(() => {
        arc.style.strokeDashoffset = offset;
      });

      // 피부 타입
      const st = sk.skin_type || {};
      document.getElementById("skin-emoji").textContent = st.emoji || "";
      document.getElementById("skin-type-name").textContent = st.name || "";
      document.getElementById("skin-type-desc").textContent = st.description || "";

      // 상세 항목
      const $metrics = document.getElementById("metrics-grid");
      const condKeys = ["brightness", "evenness", "redness", "texture", "moisture", "oiliness"];
      $metrics.innerHTML = condKeys.map(key => {
        const c = sk.conditions[key];
        if (!c) return "";
        return `
          <div class="metric-item status-${c.status}">
            <label>
              <span>${c.label}</span>
              <span class="metric-score">${c.score}점</span>
            </label>
            <div class="metric-bar">
              <div class="metric-bar-fill" data-width="${c.score}"></div>
            </div>
            <div class="metric-detail">${c.detail}</div>
          </div>
        `;
      }).join("");

      // 바 애니메이션
      requestAnimationFrame(() => {
        document.querySelectorAll(".metric-bar-fill[data-width]").forEach(el => {
          el.style.width = el.dataset.width + "%";
        });
      });

      // 분석 방법 안내
      const $method = document.getElementById("method-note");
      if (sk.analysis_method === "deep_learning_api") {
        $method.textContent = "🧠 이 분석은 딥러닝 AI 모델을 통해 수행되었습니다.";
      } else {
        $method.textContent = "📊 기본 이미지 분석으로 수행되었습니다. 딥러닝 모델 연동 시 더 정확한 결과를 제공합니다.";
      }
    }

    // ── 스킨케어 맞춤 제품 ──
    renderProducts(data.skin_products, "skin-products", "skin-products-empty");
  }

  // ============================================================
  //  제품 카드 렌더링
  // ============================================================
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

    $grid.innerHTML = products.map(p => {
      const price = Number(p.price).toLocaleString();
      const brand = p.brand || "";
      const mall = p.mall || "";
      const category = p.category || "";

      // 태그 생성 (빈 값 제외)
      const tags = [brand, category, mall].filter(t => t).slice(0, 3);

      return `
        <a class="product-card" href="${p.link}" target="_blank" rel="noopener">
          <img class="product-card-img" src="${p.image}" alt="${p.title}"
               onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><rect fill=%22%23f0ecf0%22 width=%22100%22 height=%22100%22/><text x=%2250%22 y=%2255%22 text-anchor=%22middle%22 fill=%22%23b48ed2%22 font-size=%2228%22>🧴</text></svg>'" />
          <div class="product-card-body">
            ${brand ? `<div class="product-brand">${brand}</div>` : ""}
            <div class="product-title">${p.title}</div>
            <div class="product-price">₩${price}</div>
            <div class="product-tags">
              ${tags.map(t => `<span class="product-tag">${t}</span>`).join("")}
            </div>
          </div>
        </a>
      `;
    }).join("");
  }

  // SVG gradient 정의 (한 번만 삽입)
  function ensureScoreGradient() {
    if (document.getElementById("scoreGradient")) return;
    const svg = document.querySelector(".score-circle svg");
    if (!svg) return;
    const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
    defs.innerHTML = `
      <linearGradient id="scoreGradient" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="#c97b84" />
        <stop offset="100%" stop-color="#b48ed2" />
      </linearGradient>
    `;
    svg.prepend(defs);
  }

  // ============================================================
  //  제미나이 AI 챗봇
  // ============================================================
  const $chatModal = document.getElementById("chat-modal");
  const $btnOpenChat = document.getElementById("btn-open-chat");
  const $chatClose = document.getElementById("chat-close");
  const $chatMessages = document.getElementById("chat-messages");
  const $chatInput = document.getElementById("chat-input");
  const $btnSendChat = document.getElementById("btn-send-chat");
  const $chatOverlay = document.getElementById("chat-overlay");

  let chatHistory = [];
  
  // 현재 진단 결과를 문자열로 변환하여 제미나이에게 전달할 컨텍스트 생성
  function getDiagnosisContext() {
    const pcSeason = document.getElementById("color-season")?.textContent;
    const skScore = document.getElementById("score-number")?.textContent;
    if (!pcSeason || pcSeason === "-") return "아직 진단 결과가 없습니다.";
    
    return `퍼스널컬러 진단 결과: ${pcSeason}\n피부 상태 점수: ${skScore}점\n위 결과를 바탕으로 사용자의 질문에 답해주세요.`;
  }

  function appendMessage(role, text) {
    const isUser = role === "user";
    const div = document.createElement("div");
    div.className = `chat-msg ${isUser ? "chat-user" : "chat-ai"}`;
    // 간단한 마크다운 문법 (굵게, 줄바꿈) 처리
    let formattedText = text.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    formattedText = formattedText.replace(/\n/g, "<br>");
    div.innerHTML = formattedText;
    
    $chatMessages.appendChild(div);
    $chatMessages.scrollTop = $chatMessages.scrollHeight;
  }

  function openChat() {
    $chatModal.classList.remove("hidden");
    if (chatHistory.length === 0) {
      $chatMessages.innerHTML = "";
      appendMessage("model", "안녕하세요! ✨\n진단하신 뷰티/피부 결과를 바탕으로 맞춤 화장품, 코디법, 스킨케어 팁에 대해 자유롭게 물어보세요!");
    }
  }

  function closeChat() {
    $chatModal.classList.add("hidden");
  }

  async function sendChatMessage() {
    const text = $chatInput.value.trim();
    if (!text) return;

    appendMessage("user", text);
    $chatInput.value = "";
    $chatInput.disabled = true;
    $btnSendChat.disabled = true;

    const loadingId = "loading-" + Date.now();
    const loadingDiv = document.createElement("div");
    loadingDiv.id = loadingId;
    loadingDiv.className = "chat-msg chat-ai";
    loadingDiv.innerHTML = "<span style='color: var(--text-muted)'>답변 작성중... 💭</span>";
    $chatMessages.appendChild(loadingDiv);
    $chatMessages.scrollTop = $chatMessages.scrollHeight;

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          context: getDiagnosisContext(),
          history: chatHistory
        })
      });
      
      const data = await res.json();
      document.getElementById(loadingId).remove();

      if (!data.success) {
        appendMessage("model", "⚠️ " + (data.error || "응답 오류가 발생했습니다. 제미나이 API 키를 확인해주세요."));
        return;
      }

      appendMessage("model", data.response);
      chatHistory.push({ role: "user", text: text });
      chatHistory.push({ role: "model", text: data.response });

    } catch (e) {
      document.getElementById(loadingId)?.remove();
      appendMessage("model", "⚠️ 네트워크 오류가 발생했습니다.");
    } finally {
      $chatInput.disabled = false;
      $btnSendChat.disabled = false;
      $chatInput.focus();
    }
  }

  if ($btnOpenChat) $btnOpenChat.addEventListener("click", openChat);
  if ($chatClose) $chatClose.addEventListener("click", closeChat);
  if ($chatOverlay) $chatOverlay.addEventListener("click", closeChat);
  
  if ($btnSendChat) $btnSendChat.addEventListener("click", sendChatMessage);
  if ($chatInput) {
    $chatInput.addEventListener("keydown", (e) => {
      // 한글 입력 중 엔터 눌림 방지를 위해 isComposing 확인
      if (e.key === "Enter" && !e.isComposing) {
        e.preventDefault();
        sendChatMessage();
      }
    });
  }

});
