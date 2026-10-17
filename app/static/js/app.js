/**
 * HandWriteMe - Application Controller
 * Handles SPA navigation, canvas stroke capture, document ingestion,
 * generation preview, approval gate, and PDF export.
 */

document.addEventListener("DOMContentLoaded", () => {
  // --- APPLICATION STATE ---
  const state = {
    currentView: "dashboard",
    profiles: [],
    documents: [],
    selectedProfile: null,
    selectedDocument: null,
    approvalDocument: null,
    preview: {
      documentId: null,
      pages: [],
      currentPage: 0,
    },
    canvasStrokes: [],
    isDrawing: false,
    currentUser: null,
  };

  // --- DOM ELEMENT REFERENCES ---
  const navItems = document.querySelectorAll(".nav-item");
  const viewSections = document.querySelectorAll(".view-section");
  const toastContainer = document.getElementById("toastContainer");
  const apiStatusDot = document.getElementById("apiStatusDot");
  const apiStatusText = document.getElementById("apiStatusText");
  const userDisplay = document.getElementById("userDisplay");
  const authBtn = document.getElementById("authBtn");
  const loginModal = document.getElementById("loginModal");
  const btnCloseLogin = document.getElementById("btnCloseLogin");
  const loginForm = document.getElementById("loginForm");
  const loginErrorBox = document.getElementById("loginErrorBox");
  const loginPromptNotice = document.getElementById("loginPromptNotice");
  const btnSubmitLogin = document.getElementById("btnSubmitLogin");
  const themeToggleBtn = document.getElementById("themeToggleBtn");
  const themeToggleIcon = document.getElementById("themeToggleIcon");
  const themeToggleText = document.getElementById("themeToggleText");

  // Mobile navigation elements
  const mobileMenuBtn = document.getElementById("mobileMenuBtn");
  const closeSidebarBtn = document.getElementById("closeSidebarBtn");
  const sidebarBackdrop = document.getElementById("sidebarBackdrop");
  const appSidebar = document.getElementById("appSidebar");

  // Dashboard elements
  const statProfilesCount = document.getElementById("statProfilesCount");
  const statProfilesBadge = document.getElementById("statProfilesBadge");
  const statDocsCount = document.getElementById("statDocsCount");
  const statDocsBadge = document.getElementById("statDocsBadge");
  const statApprovedCount = document.getElementById("statApprovedCount");
  const statApprovedBadge = document.getElementById("statApprovedBadge");
  const recentDocsTableContainer = document.getElementById("recentDocsTableContainer");
  const btnRefreshDashboard = document.getElementById("btnRefreshDashboard");

  // Profile elements
  const profileForm = document.getElementById("profileForm");
  const profileFormTitle = document.getElementById("profileFormTitle");
  const profileIdInput = document.getElementById("profileIdInput");
  const profileNameInput = document.getElementById("profileNameInput");
  const profileDescInput = document.getElementById("profileDescInput");
  const btnResetProfileForm = document.getElementById("btnResetProfileForm");
  const strokeCanvas = document.getElementById("strokeCanvas");
  const btnClearCanvas = document.getElementById("btnClearCanvas");
  const strokePointCount = document.getElementById("strokePointCount");
  const profilesList = document.getElementById("profilesList");
  const btnRefreshProfiles = document.getElementById("btnRefreshProfiles");
  const selectedProfileName = document.getElementById("selectedProfileName");
  const selectedProfileStatus = document.getElementById("selectedProfileStatus");
  const sampleDropzone = document.getElementById("sampleDropzone");
  const sampleFileInput = document.getElementById("sampleFileInput");
  const sampleGallery = document.getElementById("sampleGallery");

  // Document elements
  const docDropzone = document.getElementById("docDropzone");
  const docFileInput = document.getElementById("docFileInput");
  const manualDocTitle = document.getElementById("manualDocTitle");
  const manualDocContent = document.getElementById("manualDocContent");
  const btnSaveManualDoc = document.getElementById("btnSaveManualDoc");
  const documentsList = document.getElementById("documentsList");
  const btnRefreshDocs = document.getElementById("btnRefreshDocs");
  const selectedDocTitle = document.getElementById("selectedDocTitle");
  const selectedDocStatus = document.getElementById("selectedDocStatus");
  const selectedDocText = document.getElementById("selectedDocText");
  const selectedDocStats = document.getElementById("selectedDocStats");
  const btnUpdateDocText = document.getElementById("btnUpdateDocText");

  // Generation elements
  const genDocSelect = document.getElementById("genDocSelect");
  const genProfileSelect = document.getElementById("genProfileSelect");
  const genInkColor = document.getElementById("genInkColor");
  const genFontSize = document.getElementById("genFontSize");
  const fontScaleVal = document.getElementById("fontScaleVal");
  const genRandomness = document.getElementById("genRandomness");
  const jitterVal = document.getElementById("jitterVal");
  const genSlant = document.getElementById("genSlant");
  const slantVal = document.getElementById("slantVal");
  const btnGeneratePreview = document.getElementById("btnGeneratePreview");
  const btnPrevPage = document.getElementById("btnPrevPage");
  const btnNextPage = document.getElementById("btnNextPage");
  const pageIndicator = document.getElementById("pageIndicator");
  const previewStatusBadge = document.getElementById("previewStatusBadge");
  const svgContainer = document.getElementById("svgContainer");
  const btnProceedToApproval = document.getElementById("btnProceedToApproval");

  // Approval elements
  const approvalDocSelect = document.getElementById("approvalDocSelect");
  const apprDocStatus = document.getElementById("apprDocStatus");
  const apprDocPages = document.getElementById("apprDocPages");
  const apprDocWords = document.getElementById("apprDocWords");
  const approvalNotes = document.getElementById("approvalNotes");
  const btnApproveDoc = document.getElementById("btnApproveDoc");
  const btnRejectDoc = document.getElementById("btnRejectDoc");
  const btnExportPdf = document.getElementById("btnExportPdf");

  // --- TOAST NOTIFICATIONS ---
  function showToast(message, type = "success") {
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    const icon = type === "success" ? "✓" : "⚠";
    toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;
    toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(20px)";
      toast.style.transition = "all 0.3s ease";
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // --- THEME MANAGEMENT ---
  const THEME_STORAGE_KEY = "handwriteme_theme";

  function getStoredTheme() {
    try {
      return localStorage.getItem(THEME_STORAGE_KEY) || "dark";
    } catch (e) {
      return "dark";
    }
  }

  function applyTheme(theme, notify = false) {
    const isLight = theme === "light";
    const resolvedTheme = isLight ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", resolvedTheme);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, resolvedTheme);
    } catch (e) {
      // Fallback if localStorage access is restricted
    }

    if (themeToggleBtn) {
      themeToggleBtn.setAttribute(
        "aria-label",
        isLight ? "Switch to dark theme" : "Switch to light theme"
      );
      themeToggleBtn.setAttribute(
        "title",
        isLight ? "Switch to dark theme (currently light)" : "Switch to light theme (currently dark)"
      );
    }
    if (themeToggleIcon) {
      themeToggleIcon.textContent = isLight ? "🌙" : "☀️";
    }
    if (themeToggleText) {
      themeToggleText.textContent = isLight ? "Dark" : "Light";
    }

    if (typeof redrawCanvas === "function" && strokeCanvas) {
      try {
        redrawCanvas();
      } catch (err) {
        // canvas redraw optional
      }
    }

    if (notify) {
      showToast(`Switched to ${isLight ? "Light" : "Dark"} theme`, "success");
    }
  }

  function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute("data-theme") || "dark";
    const nextTheme = currentTheme === "light" ? "dark" : "light";
    applyTheme(nextTheme, true);
  }

  if (themeToggleBtn) {
    themeToggleBtn.addEventListener("click", toggleTheme);
  }

  // Initialize toggle button state based on early applied theme
  const initialTheme = document.documentElement.getAttribute("data-theme") || getStoredTheme();
  applyTheme(initialTheme, false);

  // --- RESPONSIVE MOBILE SIDEBAR DRAWER ---
  function openMobileSidebar() {
    if (!appSidebar) return;
    appSidebar.classList.add("open");
    if (sidebarBackdrop) sidebarBackdrop.classList.add("active");
    if (mobileMenuBtn) mobileMenuBtn.setAttribute("aria-expanded", "true");
    if (closeSidebarBtn) {
      closeSidebarBtn.focus();
    }
  }

  function closeMobileSidebar() {
    if (!appSidebar) return;
    appSidebar.classList.remove("open");
    if (sidebarBackdrop) sidebarBackdrop.classList.remove("active");
    if (mobileMenuBtn) {
      mobileMenuBtn.setAttribute("aria-expanded", "false");
    }
  }

  if (mobileMenuBtn) {
    mobileMenuBtn.addEventListener("click", () => {
      const isOpen = appSidebar && appSidebar.classList.contains("open");
      if (isOpen) {
        closeMobileSidebar();
      } else {
        openMobileSidebar();
      }
    });
  }

  if (closeSidebarBtn) {
    closeSidebarBtn.addEventListener("click", closeMobileSidebar);
  }

  if (sidebarBackdrop) {
    sidebarBackdrop.addEventListener("click", closeMobileSidebar);
  }

  // Close drawer on Escape key press
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (appSidebar && appSidebar.classList.contains("open")) {
        closeMobileSidebar();
        if (mobileMenuBtn) mobileMenuBtn.focus();
      }
      if (loginModal && loginModal.style.display !== "none") {
        loginModal.style.display = "none";
      }
    }
  });

  // Automatically close mobile sidebar when window expands to desktop size
  window.addEventListener("resize", () => {
    if (window.innerWidth >= 1024) {
      closeMobileSidebar();
    }
  });

  // --- NAVIGATION CONTROLLER ---
  function switchView(viewName) {
    // Automatically close mobile drawer upon navigation
    closeMobileSidebar();

    state.currentView = viewName;
    navItems.forEach((item) => {
      item.classList.toggle("active", item.dataset.view === viewName);
    });
    viewSections.forEach((section) => {
      section.classList.toggle("active", section.id === `view-${viewName}`);
    });

    if (viewName === "dashboard") refreshDashboard();
    if (viewName === "profiles") {
      refreshProfiles();
      // Ensure canvas is resized and redrawn when profiles tab becomes visible
      requestAnimationFrame(() => {
        resizeCanvas();
      });
    }
    if (viewName === "documents") refreshDocuments();
    if (viewName === "generation") syncGenerationDropdowns();
    if (viewName === "approval") syncApprovalDropdowns();
  }

  navItems.forEach((item) => {
    item.addEventListener("click", () => switchView(item.dataset.view));
  });

  document.getElementById("brandLink").addEventListener("click", (e) => {
    e.preventDefault();
    switchView("dashboard");
  });

  // --- CANVAS DRAWING PAD (STROKE CAPTURE) ---
  const ctx = strokeCanvas.getContext("2d", { willReadFrequently: false });
  let currentStroke = [];
  const strokeColor = "#0f172a"; // Deep rich dark ink, high contrast on white background
  const strokeWidth = 2.8;
  const guidelineColor = "rgba(99, 102, 241, 0.15)";

  function resizeCanvas() {
    const rect = strokeCanvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;

    // Use parent wrapper width if element was hidden or has zero width
    const parentWidth = strokeCanvas.parentElement ? strokeCanvas.parentElement.clientWidth : 0;
    const cssWidth = rect.width > 0 ? rect.width : (parentWidth > 0 ? parentWidth : 600);
    const cssHeight = rect.height > 0 ? rect.height : 220;

    if (cssWidth <= 0 || cssHeight <= 0) {
      return;
    }

    const targetWidth = Math.round(cssWidth * dpr);
    const targetHeight = Math.round(cssHeight * dpr);

    if (strokeCanvas.width !== targetWidth || strokeCanvas.height !== targetHeight) {
      strokeCanvas.width = targetWidth;
      strokeCanvas.height = targetHeight;
    }

    // Set transform so all drawing coordinates map directly to logical CSS pixels
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    redrawCanvas();
  }

  function getCanvasCoords(e) {
    const rect = strokeCanvas.getBoundingClientRect();
    let clientX = e.clientX;
    let clientY = e.clientY;

    if (clientX === undefined && e.touches && e.touches.length > 0) {
      clientX = e.touches[0].clientX;
      clientY = e.touches[0].clientY;
    } else if (clientX === undefined && e.changedTouches && e.changedTouches.length > 0) {
      clientX = e.changedTouches[0].clientX;
      clientY = e.changedTouches[0].clientY;
    }

    if (clientX === undefined || clientY === undefined) {
      return { x: 0, y: 0 };
    }

    // Map screen coordinate to canvas coordinate in logical CSS pixels
    const relX = clientX - rect.left;
    const relY = clientY - rect.top;

    // Clamp coordinates to stay within the canvas frame
    const clampedX = Math.max(0, Math.min(rect.width > 0 ? rect.width : 600, relX));
    const clampedY = Math.max(0, Math.min(rect.height > 0 ? rect.height : 220, relY));

    return {
      x: Math.round(clampedX),
      y: Math.round(clampedY),
    };
  }

  function redrawCanvas() {
    const dpr = window.devicePixelRatio || 1;
    const rect = strokeCanvas.getBoundingClientRect();
    const width = rect.width > 0 ? rect.width : (strokeCanvas.width / dpr);
    const height = rect.height > 0 ? rect.height : (strokeCanvas.height / dpr);

    // Clear entire canvas buffer safely
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, strokeCanvas.width, strokeCanvas.height);
    ctx.restore();

    // Re-apply scale
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    // Draw handwriting reference ruled lines
    ctx.save();
    ctx.strokeStyle = guidelineColor;
    ctx.lineWidth = 1;
    for (let y = 45; y < height; y += 45) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }
    ctx.restore();

    // Render all saved stroke paths
    if (state.canvasStrokes && state.canvasStrokes.length > 0) {
      ctx.save();
      ctx.strokeStyle = strokeColor;
      ctx.fillStyle = strokeColor;
      ctx.lineWidth = strokeWidth;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";

      state.canvasStrokes.forEach((stroke) => {
        if (!stroke || stroke.length === 0) return;
        if (stroke.length === 1) {
          ctx.beginPath();
          ctx.arc(stroke[0].x, stroke[0].y, strokeWidth / 2, 0, Math.PI * 2);
          ctx.fill();
        } else {
          ctx.beginPath();
          ctx.moveTo(stroke[0].x, stroke[0].y);
          for (let i = 1; i < stroke.length; i++) {
            ctx.lineTo(stroke[i].x, stroke[i].y);
          }
          ctx.stroke();
        }
      });
      ctx.restore();
    }
  }

  function startStroke(e) {
    if (e.cancelable) e.preventDefault();
    state.isDrawing = true;
    currentStroke = [];
    const pt = getCanvasCoords(e);
    currentStroke.push(pt);

    // Immediate ink mark on click/tap so user sees visible feedback instantly
    const dpr = window.devicePixelRatio || 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.save();
    ctx.fillStyle = strokeColor;
    ctx.beginPath();
    ctx.arc(pt.x, pt.y, strokeWidth / 2, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  function moveStroke(e) {
    if (!state.isDrawing) return;
    if (e.cancelable) e.preventDefault();
    const pt = getCanvasCoords(e);

    if (currentStroke.length > 0) {
      const prev = currentStroke[currentStroke.length - 1];
      if (prev.x === pt.x && prev.y === pt.y) {
        return;
      }
    }
    currentStroke.push(pt);

    // Live continuous stroke rendering
    const dpr = window.devicePixelRatio || 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (currentStroke.length >= 2) {
      const p1 = currentStroke[currentStroke.length - 2];
      const p2 = currentStroke[currentStroke.length - 1];
      ctx.save();
      ctx.strokeStyle = strokeColor;
      ctx.lineWidth = strokeWidth;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.beginPath();
      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.stroke();
      ctx.restore();
    }
  }

  function endStroke(e) {
    if (!state.isDrawing) return;
    if (e && e.cancelable) e.preventDefault();
    state.isDrawing = false;

    if (currentStroke.length >= 1) {
      state.canvasStrokes.push(currentStroke);
    }
    currentStroke = [];

    const totalPoints = state.canvasStrokes.reduce((acc, s) => acc + s.length, 0);
    strokePointCount.textContent = `${state.canvasStrokes.length} stroke(s), ${totalPoints} points recorded`;
  }

  // Pointer event listeners (supporting mouse, stylus pen, and touch seamlessly)
  if (window.PointerEvent) {
    strokeCanvas.addEventListener("pointerdown", (e) => {
      try {
        strokeCanvas.setPointerCapture(e.pointerId);
      } catch (_) {}
      startStroke(e);
    });
    strokeCanvas.addEventListener("pointermove", moveStroke);
    strokeCanvas.addEventListener("pointerup", (e) => {
      try {
        strokeCanvas.releasePointerCapture(e.pointerId);
      } catch (_) {}
      endStroke(e);
    });
    strokeCanvas.addEventListener("pointercancel", (e) => {
      try {
        strokeCanvas.releasePointerCapture(e.pointerId);
      } catch (_) {}
      endStroke(e);
    });
  } else {
    // Mouse events
    strokeCanvas.addEventListener("mousedown", startStroke);
    strokeCanvas.addEventListener("mousemove", moveStroke);
    window.addEventListener("mouseup", endStroke);

    // Touch events
    strokeCanvas.addEventListener("touchstart", startStroke, { passive: false });
    strokeCanvas.addEventListener("touchmove", moveStroke, { passive: false });
    window.addEventListener("touchend", endStroke);
    window.addEventListener("touchcancel", endStroke);
  }

  // Observe container size changes (e.g. view transitions, window resizing)
  if (window.ResizeObserver && strokeCanvas.parentElement) {
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect.width > 0 && entry.contentRect.height > 0) {
          resizeCanvas();
        }
      }
    });
    resizeObserver.observe(strokeCanvas.parentElement);
  }

  btnClearCanvas.addEventListener("click", () => {
    state.canvasStrokes = [];
    currentStroke = [];
    strokePointCount.textContent = "0 strokes recorded";
    redrawCanvas();
    showToast("Calibration pad cleared");
  });

  // --- HEALTH & AUTHENTICATION ---
  async function checkBackendHealth() {
    const isHealthy = await api.checkHealth();
    if (isHealthy) {
      apiStatusDot.classList.remove("offline");
      apiStatusText.textContent = "Connected (MSFLib)";
    } else {
      apiStatusDot.classList.add("offline");
      apiStatusText.textContent = "Offline / Error";
    }
  }

  const tabSignIn = document.getElementById("tabSignIn");
  const tabSignUp = document.getElementById("tabSignUp");
  const registerForm = document.getElementById("registerForm");
  const authModalTitle = document.getElementById("authModalTitle");
  const authHelperNotice = document.getElementById("authHelperNotice");
  const btnSubmitRegister = document.getElementById("btnSubmitRegister");

  function setAuthMode(mode) {
    if (loginErrorBox) {
      loginErrorBox.style.display = "none";
      loginErrorBox.textContent = "";
    }
    if (mode === "signup") {
      if (tabSignUp) {
        tabSignUp.style.background = "var(--accent-indigo)";
        tabSignUp.style.color = "white";
      }
      if (tabSignIn) {
        tabSignIn.style.background = "var(--bg-card)";
        tabSignIn.style.color = "var(--text-muted)";
      }
      if (loginForm) loginForm.style.display = "none";
      if (registerForm) registerForm.style.display = "block";
      if (authModalTitle) authModalTitle.textContent = "Create an Account";
      if (loginPromptNotice) loginPromptNotice.textContent = "Sign up for a new HandWriteMe account with your personal workspace.";
      if (authHelperNotice) authHelperNotice.textContent = "New users receive an isolated personal workspace for private handwriting synthesis.";
      const signupEmail = document.getElementById("signupEmail");
      if (signupEmail) setTimeout(() => signupEmail.focus(), 60);
    } else {
      if (tabSignIn) {
        tabSignIn.style.background = "var(--accent-indigo)";
        tabSignIn.style.color = "white";
      }
      if (tabSignUp) {
        tabSignUp.style.background = "var(--bg-card)";
        tabSignUp.style.color = "var(--text-muted)";
      }
      if (loginForm) loginForm.style.display = "block";
      if (registerForm) registerForm.style.display = "none";
      if (authModalTitle) authModalTitle.textContent = "Sign In to HandWriteMe";
      if (loginPromptNotice) loginPromptNotice.textContent = "Authenticate with your account to manage profiles, documents, and synthesis.";
      if (authHelperNotice) authHelperNotice.textContent = "Sign in to access your handwriting profiles, documents, and synthesis.";
      const emailInput = document.getElementById("loginEmail");
      if (emailInput) setTimeout(() => emailInput.focus(), 60);
    }
  }

  if (tabSignIn) {
    tabSignIn.addEventListener("click", () => setAuthMode("signin"));
  }
  if (tabSignUp) {
    tabSignUp.addEventListener("click", () => setAuthMode("signup"));
  }

  function openLoginModal(message = "", mode = "signin") {
    setAuthMode(mode);
    if (loginPromptNotice && message) {
      loginPromptNotice.textContent = message;
    }
    if (loginErrorBox) {
      loginErrorBox.style.display = "none";
      loginErrorBox.textContent = "";
    }
    loginModal.style.display = "flex";
  }

  function requireAuth(message = "Please sign in with your account to proceed.") {
    if (!api.getToken()) {
      openLoginModal(message);
      showToast(message, "error");
      return false;
    }
    return true;
  }

  async function checkCurrentUser() {
    if (!api.getToken()) {
      userDisplay.textContent = "Guest Mode";
      authBtn.textContent = "Login";
      state.currentUser = null;
      return null;
    }
    try {
      const me = await api.getMe();
      state.currentUser = me;
      userDisplay.textContent = me.email || me.name || "Authenticated";
      authBtn.textContent = "Logout";
      return me;
    } catch (err) {
      console.warn("Auth token invalid or expired:", err);
      api.setToken(null);
      userDisplay.textContent = "Guest Mode";
      authBtn.textContent = "Login";
      state.currentUser = null;
      return null;
    }
  }

  window.addEventListener("auth:unauthorized", () => {
    state.currentUser = null;
    state.profiles = [];
    state.documents = [];
    userDisplay.textContent = "Guest Mode";
    authBtn.textContent = "Login";
    renderProfilesList([]);
    renderDocumentsList([]);
    openLoginModal("Your session has expired. Please sign in again.");
    showToast("Session expired. Please sign in.", "error");
  });

  authBtn.addEventListener("click", () => {
    if (api.getToken()) {
      api.logout();
      state.currentUser = null;
      state.profiles = [];
      state.documents = [];
      state.selectedProfile = null;
      state.selectedDocument = null;
      userDisplay.textContent = "Guest Mode";
      authBtn.textContent = "Login";
      showToast("Logged out successfully");
      renderProfilesList([]);
      renderDocumentsList([]);
      refreshDashboard();
    } else {
      openLoginModal("Sign in or create an account to start synthesizing handwriting.");
    }
  });

  btnCloseLogin.addEventListener("click", () => {
    loginModal.style.display = "none";
  });

  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const emailInput = document.getElementById("loginEmail");
    const passInput = document.getElementById("loginPassword");
    const email = emailInput.value.trim();
    const pass = passInput.value;

    if (!email || !pass) {
      if (loginErrorBox) {
        loginErrorBox.style.display = "block";
        loginErrorBox.textContent = "Please provide both email and password.";
      }
      return;
    }

    if (loginErrorBox) {
      loginErrorBox.style.display = "none";
      loginErrorBox.textContent = "";
    }
    if (btnSubmitLogin) {
      btnSubmitLogin.disabled = true;
      btnSubmitLogin.textContent = "Signing In...";
    }

    try {
      await api.login(email, pass);
      loginModal.style.display = "none";
      showToast(`Signed in successfully as ${email}`);
      await checkCurrentUser();
      await refreshDashboard();
      await refreshProfiles();
      await refreshDocuments();
    } catch (err) {
      console.error("Authentication error:", err);
      if (loginErrorBox) {
        loginErrorBox.style.display = "block";
        let msg = err.message || "Authentication failed.";
        if (msg.includes("400") || msg.toLowerCase().includes("incorrect")) {
          msg = "Incorrect email or password. Please verify your credentials.";
        }
        loginErrorBox.textContent = msg;
      }
      showToast("Authentication failed", "error");
      passInput.value = "";
      passInput.focus();
    } finally {
      if (btnSubmitLogin) {
        btnSubmitLogin.disabled = false;
        btnSubmitLogin.textContent = "Sign In";
      }
    }
  });

  if (registerForm) {
    registerForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const nameInput = document.getElementById("signupName");
      const emailInput = document.getElementById("signupEmail");
      const passInput = document.getElementById("signupPassword");
      const confirmInput = document.getElementById("signupPasswordConfirm");

      const fullName = nameInput ? nameInput.value.trim() : "";
      const email = emailInput ? emailInput.value.trim() : "";
      const password = passInput ? passInput.value : "";
      const confirmPassword = confirmInput ? confirmInput.value : "";

      if (!email || !password || !confirmPassword) {
        if (loginErrorBox) {
          loginErrorBox.style.display = "block";
          loginErrorBox.textContent = "Please provide email, password, and password confirmation.";
        }
        return;
      }

      if (password.length < 8) {
        if (loginErrorBox) {
          loginErrorBox.style.display = "block";
          loginErrorBox.textContent = "Password must be at least 8 characters long.";
        }
        return;
      }

      if (password !== confirmPassword) {
        if (loginErrorBox) {
          loginErrorBox.style.display = "block";
          loginErrorBox.textContent = "Passwords do not match. Please verify your password.";
        }
        return;
      }

      if (loginErrorBox) {
        loginErrorBox.style.display = "none";
        loginErrorBox.textContent = "";
      }

      if (btnSubmitRegister) {
        btnSubmitRegister.disabled = true;
        btnSubmitRegister.textContent = "Creating Account...";
      }

      try {
        await api.register({
          email: email,
          password: password,
          password_confirm: confirmPassword,
          full_name: fullName || undefined,
        });

        showToast("Account created successfully! Signing in...");

        // Automatically log in with the new credentials
        await api.login(email, password);
        loginModal.style.display = "none";
        showToast(`Welcome to HandWriteMe, ${fullName || email}!`);
        await checkCurrentUser();
        await refreshDashboard();
        await refreshProfiles();
        await refreshDocuments();
      } catch (err) {
        console.error("Registration error:", err);
        if (loginErrorBox) {
          loginErrorBox.style.display = "block";
          let msg = err.message || "Registration failed.";
          if (msg.toLowerCase().includes("already exists")) {
            msg = "An account with this email address already exists. Please sign in instead.";
          }
          loginErrorBox.textContent = msg;
        }
        showToast("Registration failed", "error");
      } finally {
        if (btnSubmitRegister) {
          btnSubmitRegister.disabled = false;
          btnSubmitRegister.textContent = "Create Account";
        }
      }
    });
  }

  // --- PROFILES CONTROLLER ---
  async function refreshProfiles() {
    if (!api.getToken()) {
      profilesList.innerHTML = `
        <div style="padding: 1.5rem 1rem; text-align: center; color: var(--text-muted); font-size: 0.875rem;">
          <p style="margin-bottom: 0.75rem;">Sign in to view and manage your handwriting profiles.</p>
          <button class="btn btn-primary btn-sm btn-open-login-profiles">Sign In</button>
        </div>
      `;
      profilesList.querySelector(".btn-open-login-profiles")?.addEventListener("click", () => openLoginModal("Sign in to view and manage handwriting profiles."));
      return;
    }
    try {
      const profiles = await api.listProfiles();
      state.profiles = profiles;
      renderProfilesList(profiles);
      syncGenerationDropdowns();

      if (state.selectedProfile) {
        const found = profiles.find((p) => p.id === state.selectedProfile.id);
        if (found) selectProfile(found);
      }
    } catch (err) {
      if (err.message && err.message.toLowerCase().includes("not authenticated")) {
        return;
      }
      showToast(`Failed to load profiles: ${err.message}`, "error");
    }
  }

  function renderProfilesList(profiles) {
    if (!profiles.length) {
      profilesList.innerHTML = `<p style="color: var(--text-subtle); font-size: 0.9rem;">No profiles yet. Draw sample strokes above and click Save Profile.</p>`;
      return;
    }

    profilesList.innerHTML = profiles
      .map((p) => {
        const isSelected = state.selectedProfile && state.selectedProfile.id === p.id;
        const badgeClass = p.status === "ready" ? "badge-ready" : "badge-pending";
        return `
        <div class="card" style="padding: 0.85rem 1rem; cursor: pointer; border-color: ${isSelected ? "var(--border-focus)" : "var(--border-color)"}; background: ${isSelected ? "rgba(99, 102, 241, 0.1)" : "var(--bg-card)"}" data-profile-id="${p.id}">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;">
            <strong style="font-size: 0.95rem;">${escapeHtml(p.name)}</strong>
            <span class="badge ${badgeClass}">${p.status}</span>
          </div>
          <p style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.4rem;">${escapeHtml(p.description || "No description")}</p>
          <div style="display: flex; gap: 0.5rem; justify-content: flex-end;">
            <button class="btn btn-secondary btn-sm btn-edit-profile" data-profile-id="${p.id}">Edit</button>
            <button class="btn btn-danger btn-sm btn-del-profile" data-profile-id="${p.id}">Delete</button>
          </div>
        </div>
      `;
      })
      .join("");

    // Hook click handlers
    profilesList.querySelectorAll(".card").forEach((card) => {
      card.addEventListener("click", (e) => {
        if (e.target.closest("button")) return;
        const pId = card.dataset.profileId;
        const profile = state.profiles.find((p) => String(p.id) === String(pId));
        if (profile) selectProfile(profile);
      });
    });

    profilesList.querySelectorAll(".btn-edit-profile").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const pId = btn.dataset.profileId;
        const profile = state.profiles.find((p) => String(p.id) === String(pId));
        if (profile) editProfile(profile);
      });
    });

    profilesList.querySelectorAll(".btn-del-profile").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const pId = btn.dataset.profileId;
        if (!confirm("Are you sure you want to delete this handwriting profile?")) return;
        try {
          await api.deleteProfile(pId);
          showToast("Profile deleted", "success");
          if (state.selectedProfile && String(state.selectedProfile.id) === String(pId)) {
            state.selectedProfile = null;
            selectedProfileName.textContent = "Select a profile";
            selectedProfileStatus.textContent = "None";
            sampleGallery.innerHTML = "";
          }
          refreshProfiles();
        } catch (err) {
          showToast(err.message, "error");
        }
      });
    });
  }

  function selectProfile(profile) {
    state.selectedProfile = profile;
    selectedProfileName.textContent = profile.name;
    selectedProfileStatus.textContent = profile.status;
    selectedProfileStatus.className = `badge ${profile.status === "ready" ? "badge-ready" : "badge-pending"}`;
    renderProfilesList(state.profiles);
    loadProfileSamples(profile.id);
  }

  function editProfile(profile) {
    profileIdInput.value = profile.id;
    profileNameInput.value = profile.name;
    profileDescInput.value = profile.description || "";
    profileFormTitle.textContent = "Edit Profile: " + profile.name;
    btnResetProfileForm.style.display = "inline-flex";

    // Load strokes if available from canvas_strokes_json or canvas_strokes
    if (profile.canvas_strokes_json) {
      try {
        state.canvasStrokes = JSON.parse(profile.canvas_strokes_json);
      } catch (_) {
        state.canvasStrokes = [];
      }
    } else if (profile.canvas_strokes && Array.isArray(profile.canvas_strokes)) {
      state.canvasStrokes = profile.canvas_strokes;
    } else {
      state.canvasStrokes = [];
    }

    const totalPoints = state.canvasStrokes.reduce((acc, s) => acc + (Array.isArray(s) ? s.length : 1), 0);
    strokePointCount.textContent = `${state.canvasStrokes.length} stroke(s) loaded (${totalPoints} points)`;
    redrawCanvas();
  }

  btnResetProfileForm.addEventListener("click", () => {
    profileIdInput.value = "";
    profileForm.reset();
    profileFormTitle.textContent = "Create New Profile";
    btnResetProfileForm.style.display = "none";
    state.canvasStrokes = [];
    strokePointCount.textContent = "0 strokes recorded";
    redrawCanvas();
  });

  profileForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!requireAuth("Please sign in to save a handwriting profile.")) return;
    const id = profileIdInput.value;
    const name = profileNameInput.value.trim();
    const description = profileDescInput.value.trim();

    const hasStrokes = state.canvasStrokes && state.canvasStrokes.length > 0;
    const strokesJson = hasStrokes ? JSON.stringify(state.canvasStrokes) : null;

    const payload = {
      name,
      description,
      is_canvas_style: hasStrokes,
      canvas_strokes_json: strokesJson,
      status: hasStrokes ? "ready" : "pending",
    };

    try {
      if (id) {
        await api.updateProfile(id, payload);
        showToast("Profile updated successfully");
      } else {
        const created = await api.createProfile(payload);
        showToast("Profile created successfully");
        selectProfile(created);
      }
      btnResetProfileForm.click();
      refreshProfiles();
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // --- SAMPLES CONTROLLER ---
  async function loadProfileSamples(profileId) {
    try {
      const samples = await api.listSamples(profileId);
      renderSamplesGallery(profileId, samples);
    } catch (err) {
      showToast(`Failed to load samples: ${err.message}`, "error");
    }
  }

  function renderSamplesGallery(profileId, samples) {
    if (!samples.length) {
      sampleGallery.innerHTML = `<p style="font-size: 0.8rem; color: var(--text-subtle);">No handwriting image samples uploaded yet.</p>`;
      return;
    }

    sampleGallery.innerHTML = samples
      .map((s) => {
        const fileUrl = api.getSampleFileUrl(profileId, s.id);
        return `
        <div style="position: relative; width: 80px; height: 80px; border-radius: var(--radius-sm); overflow: hidden; border: 1px solid var(--border-color); background: #fff;">
          <img src="${fileUrl}" alt="${escapeHtml(s.label || "sample")}" style="width: 100%; height: 100%; object-fit: cover;">
          <button class="btn-del-sample" data-sample-id="${s.id}" style="position: absolute; top: 2px; right: 2px; background: rgba(0,0,0,0.6); color: #fff; border: none; border-radius: 50%; width: 20px; height: 20px; font-size: 11px; cursor: pointer;">&times;</button>
        </div>
      `;
      })
      .join("");

    sampleGallery.querySelectorAll(".btn-del-sample").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const sampleId = btn.dataset.sampleId;
        try {
          await api.deleteSample(profileId, sampleId);
          showToast("Sample removed");
          loadProfileSamples(profileId);
          refreshProfiles();
        } catch (err) {
          showToast(err.message, "error");
        }
      });
    });
  }

  sampleDropzone.addEventListener("click", () => {
    if (!requireAuth("Please sign in to upload handwriting samples.")) return;
    if (!state.selectedProfile) {
      showToast("Please select a profile first", "error");
      return;
    }
    sampleFileInput.click();
  });

  sampleFileInput.addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file || !state.selectedProfile) return;
    if (!requireAuth("Please sign in to upload handwriting samples.")) return;
    try {
      showToast("Uploading handwriting sample...", "success");
      await api.uploadSample(state.selectedProfile.id, file, file.name);
      showToast("Sample uploaded and calibrated!");
      loadProfileSamples(state.selectedProfile.id);
      refreshProfiles();
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      sampleFileInput.value = "";
    }
  });

  // --- DOCUMENTS CONTROLLER ---
  async function refreshDocuments(selectDocId = null) {
    if (!api.getToken()) {
      documentsList.innerHTML = `
        <div style="padding: 1.5rem 1rem; text-align: center; color: var(--text-muted); font-size: 0.875rem;">
          <p style="margin-bottom: 0.75rem;">Sign in to view and ingest documents.</p>
          <button class="btn btn-primary btn-sm btn-open-login-docs">Sign In</button>
        </div>
      `;
      documentsList.querySelector(".btn-open-login-docs")?.addEventListener("click", () => openLoginModal("Sign in to view and ingest documents."));
      return;
    }
    try {
      const docs = await api.listDocuments();
      state.documents = docs || [];
      renderDocumentsList(state.documents);
      syncGenerationDropdowns();
      syncApprovalDropdowns();

      // Determine target document to select
      let targetDoc = null;
      if (selectDocId !== null && selectDocId !== undefined) {
        targetDoc = state.documents.find((d) => String(d.id) === String(selectDocId));
      } else if (state.selectedDocument) {
        targetDoc = state.documents.find((d) => String(d.id) === String(state.selectedDocument.id));
      }

      if (targetDoc) {
        selectDocument(targetDoc);
      } else if (state.documents.length > 0 && !state.selectedDocument) {
        selectDocument(state.documents[0]);
      } else if (state.documents.length === 0) {
        state.selectedDocument = null;
        selectedDocTitle.textContent = "None";
        selectedDocStatus.textContent = "none";
        selectedDocText.value = "";
        selectedDocStats.textContent = "0 words • 0 characters";
      }
    } catch (err) {
      if (err.message && err.message.toLowerCase().includes("not authenticated")) {
        return;
      }
      showToast(`Failed to load documents: ${err.message}`, "error");
    }
  }

  function renderDocumentsList(docs) {
    if (!docs.length) {
      documentsList.innerHTML = `<p style="color: var(--text-subtle); font-size: 0.9rem;">No documents found. Drop a PDF or enter text on the left.</p>`;
      return;
    }

    documentsList.innerHTML = docs
      .map((d) => {
        const isSelected = state.selectedDocument && String(state.selectedDocument.id) === String(d.id);
        const docTitle = d.title || (d.filename ? d.filename.replace(/\.[^/.]+$/, "") : "Untitled Document");
        const words = d.word_count !== undefined ? d.word_count : (d.extracted_text ? d.extracted_text.trim().split(/\s+/).filter(Boolean).length : 0);
        const pages = d.page_count || 1;
        const badgeMap = {
          extracted: "badge-extracted",
          generated: "badge-generated",
          approved: "badge-approved",
          rejected: "badge-failed",
          failed: "badge-failed",
        };
        const badgeClass = badgeMap[d.status] || "badge-pending";
        return `
        <div class="card doc-item-card" style="padding: 0.85rem 1rem; cursor: pointer; border-color: ${isSelected ? "var(--border-focus)" : "var(--border-color)"}; background: ${isSelected ? "rgba(6, 182, 212, 0.08)" : "var(--bg-card)"}" data-doc-id="${d.id}">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;">
            <strong style="font-size: 0.95rem;">${escapeHtml(docTitle)}</strong>
            <span class="badge ${badgeClass}">${escapeHtml(d.status)}</span>
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 0.8rem; color: var(--text-muted); align-items: center;">
            <span>${words} words • ${pages} pg</span>
            <div style="display: flex; gap: 0.5rem;">
              <button type="button" class="btn btn-secondary btn-sm btn-select-doc" data-doc-id="${d.id}">Inspect</button>
              <button type="button" class="btn btn-danger btn-sm btn-del-doc" data-doc-id="${d.id}">Delete</button>
            </div>
          </div>
        </div>
      `;
      })
      .join("");

    documentsList.querySelectorAll(".doc-item-card").forEach((card) => {
      card.addEventListener("click", (e) => {
        if (e.target.closest("button")) return;
        const docId = card.dataset.docId;
        const doc = state.documents.find((d) => String(d.id) === String(docId));
        if (doc) selectDocument(doc);
      });
    });

    documentsList.querySelectorAll(".btn-select-doc").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const docId = btn.dataset.docId;
        const doc = state.documents.find((d) => String(d.id) === String(docId));
        if (doc) selectDocument(doc);
      });
    });

    documentsList.querySelectorAll(".btn-del-doc").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const docId = btn.dataset.docId;
        if (!confirm("Are you sure you want to delete this document?")) return;
        try {
          await api.deleteDocument(docId);
          showToast("Document deleted", "success");
          if (state.selectedDocument && String(state.selectedDocument.id) === String(docId)) {
            state.selectedDocument = null;
            selectedDocTitle.textContent = "None";
            selectedDocStatus.textContent = "none";
            selectedDocText.value = "";
            selectedDocStats.textContent = "0 words • 0 characters";
          }
          await refreshDocuments();
        } catch (err) {
          showToast(err.message, "error");
        }
      });
    });
  }

  function selectDocument(doc) {
    if (!doc) return;
    state.selectedDocument = doc;
    const docTitle = doc.title || (doc.filename ? doc.filename.replace(/\.[^/.]+$/, "") : "Untitled Document");
    selectedDocTitle.textContent = docTitle;
    selectedDocStatus.textContent = doc.status;
    selectedDocText.value = doc.extracted_text || "";
    const words = doc.word_count !== undefined ? doc.word_count : (doc.extracted_text ? doc.extracted_text.trim().split(/\s+/).filter(Boolean).length : 0);
    const chars = doc.char_count !== undefined ? doc.char_count : (doc.extracted_text ? doc.extracted_text.length : 0);
    selectedDocStats.textContent = `${words} words • ${chars} characters`;
    renderDocumentsList(state.documents);
  }

  btnUpdateDocText.addEventListener("click", async () => {
    if (!requireAuth("Please sign in to edit document text.")) return;
    if (!state.selectedDocument) {
      showToast("No document selected", "error");
      return;
    }
    const newText = selectedDocText.value;
    try {
      btnUpdateDocText.disabled = true;
      btnUpdateDocText.textContent = "Saving...";
      const updated = await api.updateDocument(state.selectedDocument.id, {
        extracted_text: newText,
      });
      showToast("Document text updated successfully", "success");
      await refreshDocuments(updated.id);
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      btnUpdateDocText.disabled = false;
      btnUpdateDocText.textContent = "Save Text Edits";
    }
  });

  // Dropzone PDF upload
  docDropzone.addEventListener("click", () => {
    if (!requireAuth("Please sign in to upload PDF documents.")) return;
    docFileInput.click();
  });

  docDropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    docDropzone.classList.add("dragover");
  });

  docDropzone.addEventListener("dragleave", () => docDropzone.classList.remove("dragover"));

  docDropzone.addEventListener("drop", async (e) => {
    e.preventDefault();
    docDropzone.classList.remove("dragover");
    if (!requireAuth("Please sign in to upload PDF documents.")) return;
    if (e.dataTransfer.files.length) {
      handlePdfUpload(e.dataTransfer.files[0]);
    }
  });

  docFileInput.addEventListener("change", (e) => {
    if (e.target.files.length) {
      handlePdfUpload(e.target.files[0]);
    }
  });

  async function handlePdfUpload(file) {
    if (!requireAuth("Please sign in to upload PDF documents.")) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      showToast("Only PDF documents are supported for upload", "error");
      return;
    }
    try {
      showToast("Uploading and extracting text with PyPDF...", "success");
      const doc = await api.uploadDocument(file);
      showToast(`Extracted ${doc.word_count || 0} words across ${doc.page_count || 1} page(s)!`);
      refreshDocuments();
      selectDocument(doc);
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      docFileInput.value = "";
    }
  }

  // Manual Plain Text Ingestion
  btnSaveManualDoc.addEventListener("click", async () => {
    if (!requireAuth("Please sign in to ingest documents.")) return;
    const title = manualDocTitle.value.trim() || "Untitled Document";
    const text = manualDocContent.value.trim();
    if (!text) {
      showToast("Please enter some text content first", "error");
      return;
    }

    try {
      showToast("Ingesting manual text document...", "info");
      btnSaveManualDoc.disabled = true;
      btnSaveManualDoc.textContent = "Ingesting...";

      const doc = await api.createTextDocument(title, text);

      showToast("Document created from text input!", "success");
      manualDocTitle.value = "";
      manualDocContent.value = "";
      await refreshDocuments(doc.id);
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      btnSaveManualDoc.disabled = false;
      btnSaveManualDoc.textContent = "Ingest Plain Text";
    }
  });

  // --- GENERATION & MULTI-PAGE PREVIEW ---
  function syncGenerationDropdowns() {
    // Sync Documents
    const curDoc = genDocSelect.value;
    genDocSelect.innerHTML = `<option value="">-- Choose Ingested Document --</option>` +
      state.documents
        .map((d) => {
          const docTitle = d.title || (d.filename ? d.filename.replace(/\.[^/.]+$/, "") : "Untitled Document");
          const words = d.word_count !== undefined ? d.word_count : (d.extracted_text ? d.extracted_text.trim().split(/\s+/).filter(Boolean).length : 0);
          return `<option value="${d.id}" ${String(d.id) === String(curDoc) ? "selected" : ""}>${escapeHtml(docTitle)} (${words} words)</option>`;
        })
        .join("");

    // Sync Profiles
    const curProf = genProfileSelect.value;
    genProfileSelect.innerHTML = `<option value="">-- Choose Handwriting Profile --</option>` +
      state.profiles
        .map((p) => `<option value="${p.id}" ${p.id === curProf ? "selected" : ""}>${escapeHtml(p.name)} [${p.status}]</option>`)
        .join("");
  }

  // Real-time slider labels
  genFontSize.addEventListener("input", () => (fontScaleVal.textContent = `${genFontSize.value}px`));
  genRandomness.addEventListener("input", () => {
    const val = parseInt(genRandomness.value, 10);
    jitterVal.textContent = val < 3 ? "Low" : val < 7 ? "Medium" : "High";
  });
  genSlant.addEventListener("input", () => (slantVal.textContent = `${genSlant.value}°`));

  // Document selection change in Generation view: load existing preview if available
  genDocSelect.addEventListener("change", async () => {
    const docId = genDocSelect.value;
    if (!docId) {
      state.preview.documentId = null;
      state.preview.pages = [];
      state.preview.currentPage = 0;
      renderPreviewPage();
      previewStatusBadge.textContent = "No Preview Generated";
      previewStatusBadge.className = "badge badge-pending";
      btnProceedToApproval.disabled = true;
      return;
    }

    const doc = state.documents.find((d) => String(d.id) === String(docId));
    if (doc && (doc.status === "generated" || doc.status === "approved")) {
      try {
        previewStatusBadge.textContent = "Loading Preview...";
        previewStatusBadge.className = "badge badge-pending";
        const previewData = await api.getPreview(docId);
        let svgs = [];
        if (Array.isArray(previewData.preview_svgs) && previewData.preview_svgs.length > 0) {
          svgs = previewData.preview_svgs;
        } else if (Array.isArray(previewData.pages) && previewData.pages.length > 0) {
          svgs = previewData.pages.map((p) => (typeof p === "string" ? p : p.svg_content)).filter(Boolean);
        }

        if (svgs.length > 0) {
          state.preview.documentId = docId;
          state.preview.pages = svgs;
          state.preview.currentPage = 0;
          renderPreviewPage();
          btnProceedToApproval.disabled = false;
          previewStatusBadge.textContent = doc.status === "approved" ? "Approved" : "Preview Ready";
          previewStatusBadge.className = doc.status === "approved" ? "badge badge-approved" : "badge badge-generated";
          const modelNoteBox = document.getElementById("previewModelNote");
          if (modelNoteBox) {
            if (previewData && previewData.model_status_note) {
              modelNoteBox.textContent = previewData.model_status_note;
              modelNoteBox.style.display = "block";
            } else {
              modelNoteBox.style.display = "none";
            }
          }

          if (doc.selected_profile_id) {
            genProfileSelect.value = String(doc.selected_profile_id);
          }
          return;
        }
      } catch (_) {}
    }

    // Document not generated yet
    const modelNoteBox = document.getElementById("previewModelNote");
    if (modelNoteBox) modelNoteBox.style.display = "none";

    state.preview.documentId = docId;
    state.preview.pages = [];
    state.preview.currentPage = 0;
    renderPreviewPage();
    previewStatusBadge.textContent = "Not Generated";
    previewStatusBadge.className = "badge badge-pending";
    btnProceedToApproval.disabled = true;
  });

  btnGeneratePreview.addEventListener("click", async () => {
    if (!requireAuth("Please sign in to synthesize handwriting.")) return;
    const docId = genDocSelect.value;
    const profileId = genProfileSelect.value;

    if (!docId) {
      showToast("Please choose a document to synthesize", "error");
      return;
    }
    if (!profileId) {
      showToast("Please choose a handwriting profile", "error");
      return;
    }

    const options = {
      profile_id: parseInt(profileId, 10),
      ink_color: genInkColor.value,
      font_size: parseInt(genFontSize.value, 10),
      randomness: parseInt(genRandomness.value, 10) / 10,
      slant_angle: parseFloat(genSlant.value) || 0.0,
    };

    btnGeneratePreview.disabled = true;
    btnGeneratePreview.innerHTML = `<span>Synthesizing strokes...</span>`;
    previewStatusBadge.textContent = "Synthesizing...";
    previewStatusBadge.className = "badge badge-pending";

    try {
      const result = await api.generatePreview(docId, options);
      state.preview.documentId = docId;

      // Extract SVGs from preview_svgs or structured pages array
      let svgs = [];
      if (Array.isArray(result.preview_svgs) && result.preview_svgs.length > 0) {
        svgs = result.preview_svgs;
      } else if (Array.isArray(result.pages) && result.pages.length > 0) {
        svgs = result.pages.map((p) => (typeof p === "string" ? p : p.svg_content)).filter(Boolean);
      }

      if (!svgs || svgs.length === 0) {
        // Fallback: fetch preview via GET /documents/{id}/preview if not returned directly
        try {
          const previewData = await api.getPreview(docId);
          if (Array.isArray(previewData.preview_svgs) && previewData.preview_svgs.length > 0) {
            svgs = previewData.preview_svgs;
          } else if (Array.isArray(previewData.pages) && previewData.pages.length > 0) {
            svgs = previewData.pages.map((p) => (typeof p === "string" ? p : p.svg_content)).filter(Boolean);
          }
        } catch (_) {}
      }

      if (!svgs || svgs.length === 0) {
        throw new Error("No preview pages were generated. Please check document text content.");
      }

      state.preview.pages = svgs;
      state.preview.currentPage = 0;

      const modelNoteBox = document.getElementById("previewModelNote");
      if (modelNoteBox) {
        if (result && result.model_status_note) {
          modelNoteBox.textContent = result.model_status_note;
          modelNoteBox.style.display = "block";
        } else {
          modelNoteBox.style.display = "none";
        }
      }

      showToast(`Synthesized ${svgs.length} page(s) successfully!`, "success");
      renderPreviewPage();
      btnProceedToApproval.disabled = false;
      previewStatusBadge.textContent = "Preview Ready";
      previewStatusBadge.className = "badge badge-generated";
      await refreshDocuments();
    } catch (err) {
      showToast(err.message, "error");
      previewStatusBadge.textContent = "Generation Failed";
      previewStatusBadge.className = "badge badge-failed";
    } finally {
      btnGeneratePreview.disabled = false;
      btnGeneratePreview.innerHTML = `<span>Synthesize Handwriting</span>`;
    }
  });

  function renderPreviewPage() {
    const total = state.preview.pages.length;
    if (total === 0) {
      svgContainer.innerHTML = `<div style="padding: 2rem; color: var(--text-subtle); text-align: center;">No preview pages available.</div>`;
      pageIndicator.textContent = "Page 0 of 0";
      btnPrevPage.disabled = true;
      btnNextPage.disabled = true;
      return;
    }

    const currentIdx = state.preview.currentPage;
    pageIndicator.textContent = `Page ${currentIdx + 1} of ${total}`;
    btnPrevPage.disabled = currentIdx <= 0;
    btnNextPage.disabled = currentIdx >= total - 1;

    // Insert SVG into container
    svgContainer.innerHTML = state.preview.pages[currentIdx];
  }

  btnPrevPage.addEventListener("click", () => {
    if (state.preview.currentPage > 0) {
      state.preview.currentPage--;
      renderPreviewPage();
    }
  });

  btnNextPage.addEventListener("click", () => {
    if (state.preview.currentPage < state.preview.pages.length - 1) {
      state.preview.currentPage++;
      renderPreviewPage();
    }
  });

  btnProceedToApproval.addEventListener("click", () => {
    switchView("approval");
    if (state.preview.documentId) {
      approvalDocSelect.value = String(state.preview.documentId);
      approvalDocSelect.dispatchEvent(new Event("change"));
    }
  });

  // --- APPROVAL & EXPORT GATE ---
  function syncApprovalDropdowns() {
    const cur = approvalDocSelect.value || (state.approvalDocument ? String(state.approvalDocument.id) : "");
    approvalDocSelect.innerHTML = `<option value="">-- Choose Generated Document --</option>` +
      state.documents
        .map((d) => {
          const docTitle = d.title || (d.filename ? d.filename.replace(/\.[^/.]+$/, "") : "Untitled Document");
          return `<option value="${d.id}" ${String(d.id) === String(cur) ? "selected" : ""}>${escapeHtml(docTitle)} [${d.status}]</option>`;
        })
        .join("");

    if (cur) {
      const doc = state.documents.find((d) => String(d.id) === String(cur));
      if (doc) {
        state.approvalDocument = doc;
        apprDocStatus.textContent = doc.status;
        apprDocStatus.className = `badge ${doc.status === "approved" ? "badge-approved" : doc.status === "generated" ? "badge-generated" : "badge-pending"}`;
        apprDocPages.textContent = doc.page_count || 1;
        const words = doc.word_count !== undefined ? doc.word_count : (doc.extracted_text ? doc.extracted_text.trim().split(/\s+/).filter(Boolean).length : 0);
        apprDocWords.textContent = words;
        btnExportPdf.disabled = doc.status !== "approved";
      }
    }
  }

  approvalDocSelect.addEventListener("change", () => {
    const docId = approvalDocSelect.value;
    const doc = state.documents.find((d) => String(d.id) === String(docId));
    state.approvalDocument = doc || null;

    if (!doc) {
      apprDocStatus.textContent = "none";
      apprDocStatus.className = "badge badge-pending";
      apprDocPages.textContent = "0";
      apprDocWords.textContent = "0";
      btnExportPdf.disabled = true;
      return;
    }

    const words = doc.word_count !== undefined ? doc.word_count : (doc.extracted_text ? doc.extracted_text.trim().split(/\s+/).filter(Boolean).length : 0);
    apprDocStatus.textContent = doc.status;
    apprDocStatus.className = `badge ${doc.status === "approved" ? "badge-approved" : doc.status === "generated" ? "badge-generated" : "badge-pending"}`;
    apprDocPages.textContent = doc.page_count || 1;
    apprDocWords.textContent = words;

    btnExportPdf.disabled = doc.status !== "approved";
  });

  btnApproveDoc.addEventListener("click", async () => {
    if (!requireAuth("Please sign in to approve documents.")) return;
    const docId = approvalDocSelect.value || (state.approvalDocument && state.approvalDocument.id);
    if (!docId) {
      showToast("Please choose a document to approve", "error");
      return;
    }
    const notes = approvalNotes.value.trim();
    try {
      const updated = await api.approveDocument(docId, true, notes);
      showToast("Document approved for physical export!");
      state.approvalDocument = updated;
      await refreshDocuments(updated.id);
      approvalDocSelect.value = String(updated.id);
      approvalDocSelect.dispatchEvent(new Event("change"));
      refreshDashboard();
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  btnRejectDoc.addEventListener("click", async () => {
    if (!requireAuth("Please sign in to reject documents.")) return;
    const docId = approvalDocSelect.value || (state.approvalDocument && state.approvalDocument.id);
    if (!docId) {
      showToast("Please choose a document to reject", "error");
      return;
    }
    const notes = approvalNotes.value.trim();
    try {
      const updated = await api.approveDocument(docId, false, notes);
      showToast("Document rejected / marked for review", "error");
      state.approvalDocument = updated;
      await refreshDocuments(updated.id);
      approvalDocSelect.value = String(updated.id);
      approvalDocSelect.dispatchEvent(new Event("change"));
      refreshDashboard();
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  btnExportPdf.addEventListener("click", async () => {
    if (!requireAuth("Please sign in to export PDF documents.")) return;

    // Resolve target document
    const selectedId = approvalDocSelect.value || (state.approvalDocument && state.approvalDocument.id);
    if (!selectedId) {
      showToast("Please select an approved document to export.", "error");
      return;
    }

    let doc = state.approvalDocument;
    if (!doc || String(doc.id) !== String(selectedId)) {
      doc = state.documents.find((d) => String(d.id) === String(selectedId));
      state.approvalDocument = doc || null;
    }

    if (!doc) {
      showToast("Selected document not found. Please refresh the documents list.", "error");
      return;
    }

    if (doc.status !== "approved") {
      showToast(`Document "${doc.title || doc.filename}" is not approved (status: ${doc.status}). Approve it first before exporting.`, "error");
      return;
    }

    btnExportPdf.disabled = true;
    const labelSpan = btnExportPdf.querySelector("span");
    const originalText = labelSpan ? labelSpan.textContent : "Download Exported PDF";
    if (labelSpan) labelSpan.textContent = "Exporting PDF...";

    try {
      showToast("Generating compliant PDF 1.4 file...", "success");
      const blob = await api.exportDocumentPdf(doc.id);

      if (!(blob instanceof Blob)) {
        throw new Error("Invalid binary PDF response received from export endpoint.");
      }

      const docTitle = doc.title || (doc.filename ? doc.filename.replace(/\.[^/.]+$/, "") : "Document");
      const safeStem = docTitle.replace(/[^a-zA-Z0-9_\-\s]/g, "").trim().replace(/\s+/g, "_") || "Handwritten_Doc";
      const downloadFilename = `${safeStem}_Handwritten.pdf`;

      // Trigger browser download safely without immediate URL revocation
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.style.display = "none";
      a.href = url;
      a.download = downloadFilename;
      document.body.appendChild(a);
      a.click();

      // Revoke the Object URL after browser has begun handling the download stream
      setTimeout(() => {
        window.URL.revokeObjectURL(url);
        a.remove();
      }, 2000);

      showToast(`Handwritten PDF "${downloadFilename}" downloaded successfully!`);
    } catch (err) {
      console.error("Export failure:", err);
      showToast(`Export failed: ${err.message}`, "error");
    } finally {
      btnExportPdf.disabled = (doc.status !== "approved");
      if (labelSpan) labelSpan.textContent = originalText;
    }
  });


  // --- DASHBOARD CONTROLLER ---
  async function refreshDashboard() {
    if (!api.getToken()) {
      statProfilesCount.textContent = "0";
      statProfilesBadge.textContent = "Sign In";
      statProfilesBadge.className = "badge badge-pending";

      statDocsCount.textContent = "0";
      statDocsBadge.textContent = "Sign In";
      statDocsBadge.className = "badge badge-pending";

      statApprovedCount.textContent = "0";
      statApprovedBadge.textContent = "Sign In";
      statApprovedBadge.className = "badge badge-pending";

      recentDocsTableContainer.innerHTML = `
        <div style="padding: 1.75rem 1rem; text-align: center; color: var(--text-muted); font-size: 0.9rem;">
          <p style="margin-bottom: 0.85rem;">Sign in to view your handwriting profiles, documents, and generation queue.</p>
          <button class="btn btn-primary btn-sm btn-open-login-dash">Sign In Now</button>
        </div>
      `;
      recentDocsTableContainer.querySelector(".btn-open-login-dash")?.addEventListener("click", () => openLoginModal("Sign in to access your HandWriteMe workspace."));
      return;
    }
    try {
      const [profiles, docs] = await Promise.all([api.listProfiles(), api.listDocuments()]);
      state.profiles = profiles;
      state.documents = docs;

      // Stats
      statProfilesCount.textContent = profiles.length;
      const readyProfiles = profiles.filter((p) => p.status === "ready").length;
      statProfilesBadge.textContent = `${readyProfiles} Ready`;
      statProfilesBadge.className = "badge badge-ready";

      statDocsCount.textContent = docs.length;
      statDocsBadge.textContent = `${docs.length} Active`;
      statDocsBadge.className = "badge badge-extracted";

      const approvedDocs = docs.filter((d) => d.status === "approved").length;
      statApprovedCount.textContent = approvedDocs;
      statApprovedBadge.textContent = `${approvedDocs} Verified`;
      statApprovedBadge.className = "badge badge-approved";

      // Recent docs table
      if (!docs.length) {
        recentDocsTableContainer.innerHTML = `<p style="color: var(--text-subtle); font-size: 0.9rem;">No documents uploaded yet. Head over to Document Ingestion to upload your first PDF.</p>`;
        return;
      }

      recentDocsTableContainer.innerHTML = `
        <table style="width: 100%; border-collapse: collapse; font-size: 0.875rem;">
          <thead>
            <tr style="border-bottom: 1px solid var(--border-color); text-align: left; color: var(--text-muted);">
              <th style="padding: 0.75rem 0.5rem;">Document Title</th>
              <th style="padding: 0.75rem 0.5rem;">Words</th>
              <th style="padding: 0.75rem 0.5rem;">Pages</th>
              <th style="padding: 0.75rem 0.5rem;">Status</th>
              <th style="padding: 0.75rem 0.5rem; text-align: right;">Action</th>
            </tr>
          </thead>
          <tbody>
            ${docs
              .slice(0, 5)
              .map(
                (d) => {
                  const docTitle = d.title || (d.filename ? d.filename.replace(/\.[^/.]+$/, "") : "Untitled Document");
                  const words = d.word_count !== undefined ? d.word_count : (d.extracted_text ? d.extracted_text.trim().split(/\s+/).filter(Boolean).length : 0);
                  const pages = d.page_count || 1;
                  return `
              <tr style="border-bottom: 1px solid rgba(255,255,255,0.04);">
                <td style="padding: 0.75rem 0.5rem; font-weight: 500;">${escapeHtml(docTitle)}</td>
                <td style="padding: 0.75rem 0.5rem; color: var(--text-muted);">${words}</td>
                <td style="padding: 0.75rem 0.5rem; color: var(--text-muted);">${pages}</td>
                <td style="padding: 0.75rem 0.5rem;"><span class="badge ${d.status === "approved" ? "badge-approved" : d.status === "generated" ? "badge-generated" : "badge-extracted"}">${escapeHtml(d.status)}</span></td>
                <td style="padding: 0.75rem 0.5rem; text-align: right;">
                  <button type="button" class="btn btn-secondary btn-sm btn-quick-inspect" data-doc-id="${d.id}">View</button>
                </td>
              </tr>
            `;
                }
              )
              .join("")}
          </tbody>
        </table>
      `;

      recentDocsTableContainer.querySelectorAll(".btn-quick-inspect").forEach((btn) => {
        btn.addEventListener("click", () => {
          const docId = btn.dataset.docId;
          const doc = state.documents.find((d) => String(d.id) === String(docId));
          if (doc) {
            switchView("documents");
            selectDocument(doc);
          }
        });
      });
    } catch (err) {
      console.warn("Dashboard refresh error:", err);
    }
  }

  btnRefreshDashboard.addEventListener("click", async () => {
    btnRefreshDashboard.disabled = true;
    try {
      await refreshDashboard();
      showToast("Dashboard refreshed", "success");
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      btnRefreshDashboard.disabled = false;
    }
  });

  btnRefreshProfiles.addEventListener("click", async () => {
    btnRefreshProfiles.disabled = true;
    try {
      await refreshProfiles();
      showToast("Profiles list refreshed", "success");
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      btnRefreshProfiles.disabled = false;
    }
  });

  btnRefreshDocs.addEventListener("click", async () => {
    btnRefreshDocs.disabled = true;
    try {
      await refreshDocuments();
      showToast("Documents list refreshed", "success");
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      btnRefreshDocs.disabled = false;
    }
  });

  // --- UTILS ---
  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // --- INITIALIZATION ---
  window.addEventListener("resize", resizeCanvas);
  setTimeout(resizeCanvas, 100);

  checkBackendHealth();
  checkCurrentUser().finally(() => {
    refreshDashboard();
    refreshProfiles();
    refreshDocuments();
  });
});
