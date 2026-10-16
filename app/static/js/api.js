/**
 * HandWriteMe - API Client
 * Wraps MSFLib Auth and HandWriteMe REST endpoints.
 */

class ApiClient {
  constructor(baseUrl = "/api/v1") {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.token = localStorage.getItem("handwriteme_token") || null;
  }

  setToken(token) {
    this.token = token;
    if (token) {
      localStorage.setItem("handwriteme_token", token);
    } else {
      localStorage.removeItem("handwriteme_token");
    }
  }

  getToken() {
    return this.token;
  }

  getHeaders(isFormData = false) {
    const headers = {};
    if (!isFormData) {
      headers["Content-Type"] = "application/json";
    }
    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }
    return headers;
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;
    const isFormData = options.body instanceof FormData;
    const headers = { ...this.getHeaders(isFormData), ...(options.headers || {}) };

    const config = {
      ...options,
      headers,
    };

    try {
      const response = await fetch(url, config);

      if (response.status === 401) {
        // Token expired or invalid
        this.setToken(null);
        window.dispatchEvent(new CustomEvent("auth:unauthorized"));
      }

      if (!response.ok) {
        let errorDetail = `Request failed (${response.status})`;
        try {
          const errJson = await response.json();
          errorDetail = errJson.detail || errorDetail;
        } catch (_) {
          errorDetail = await response.text() || errorDetail;
        }
        throw new Error(errorDetail);
      }

      const contentType = response.headers.get("content-type") || "";
      if (contentType.includes("application/json")) {
        return await response.json();
      } else if (contentType.includes("application/pdf") || contentType.includes("image/")) {
        return await response.blob();
      }
      return await response.text();
    } catch (err) {
      console.error(`API Error [${options.method || "GET"} ${url}]:`, err);
      throw err;
    }
  }

  // --- HEALTH CHECK ---
  async checkHealth() {
    try {
      const res = await fetch(`${this.baseUrl}/openapi.json`);
      return res.ok;
    } catch (_) {
      return false;
    }
  }

  // --- AUTH ---
  async register(data) {
    const res = await fetch(`${this.baseUrl}/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });

    if (!res.ok) {
      let errDetail = "Registration failed";
      try {
        const errJson = await res.json();
        if (Array.isArray(errJson.detail)) {
          errDetail = errJson.detail.map((d) => d.msg || d.message).join(", ");
        } else if (errJson.detail) {
          errDetail = errJson.detail;
        }
      } catch (_) {}
      throw new Error(errDetail);
    }

    return await res.json();
  }

  async login(username, password) {
    const formData = new URLSearchParams();
    formData.append("username", username);
    formData.append("password", password);

    const res = await fetch(`${this.baseUrl}/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Login failed" }));
      throw new Error(err.detail || "Authentication failed");
    }

    const data = await res.json();
    this.setToken(data.access_token);
    return data;
  }

  async logout() {
    try {
      await this.request("/logout", { method: "DELETE" });
    } catch (_) {}
    this.setToken(null);
  }

  async getMe() {
    return await this.request("/me");
  }

  // --- HANDWRITING PROFILES ---
  async listProfiles() {
    return await this.request("/handwriting-profiles/");
  }

  async createProfile(data) {
    return await this.request("/handwriting-profiles/", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async getProfile(id) {
    return await this.request(`/handwriting-profiles/${id}`);
  }

  async updateProfile(id, data) {
    return await this.request(`/handwriting-profiles/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  async deleteProfile(id) {
    return await this.request(`/handwriting-profiles/${id}`, {
      method: "DELETE",
    });
  }

  // --- SAMPLES ---
  async uploadSample(profileId, file, label = "") {
    const formData = new FormData();
    formData.append("file", file);
    if (label) {
      formData.append("label", label);
    }
    return await this.request(`/handwriting-profiles/${profileId}/samples`, {
      method: "POST",
      body: formData,
    });
  }

  async listSamples(profileId) {
    return await this.request(`/handwriting-profiles/${profileId}/samples`);
  }

  async deleteSample(profileId, sampleId) {
    return await this.request(`/handwriting-profiles/${profileId}/samples/${sampleId}`, {
      method: "DELETE",
    });
  }

  getSampleFileUrl(profileId, sampleId) {
    const base = `${this.baseUrl}/handwriting-profiles/${profileId}/samples/${sampleId}/file`;
    if (this.token) {
      return `${base}?token=${encodeURIComponent(this.token)}`;
    }
    return base;
  }

  // --- DOCUMENTS ---
  async uploadDocument(file) {
    const formData = new FormData();
    formData.append("file", file);
    return await this.request("/documents/upload", {
      method: "POST",
      body: formData,
    });
  }

  async createTextDocument(title, text) {
    return await this.request("/documents/text", {
      method: "POST",
      body: JSON.stringify({ title, text }),
    });
  }

  async createDocument(data) {
    if (data.title && data.text) {
      return await this.createTextDocument(data.title, data.text);
    }
    return await this.request("/documents/", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async listDocuments() {
    return await this.request("/documents/");
  }

  async getDocument(id) {
    return await this.request(`/documents/${id}`);
  }

  async updateDocument(id, data) {
    return await this.request(`/documents/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  async deleteDocument(id) {
    return await this.request(`/documents/${id}`, {
      method: "DELETE",
    });
  }

  // --- GENERATION, PREVIEW, APPROVAL, EXPORT ---
  async generatePreview(documentId, options = {}) {
    return await this.request(`/documents/${documentId}/generate`, {
      method: "POST",
      body: JSON.stringify(options),
    });
  }

  async getPreview(documentId) {
    return await this.request(`/documents/${documentId}/preview`);
  }

  async approveDocument(documentId, approved = true, notes = "") {
    return await this.request(`/documents/${documentId}/approve`, {
      method: "POST",
      body: JSON.stringify({ approved, notes }),
    });
  }

  async exportDocumentPdf(documentId) {
    return await this.request(`/documents/${documentId}/export`, {
      method: "GET",
      headers: { Accept: "application/pdf" },
    });
  }

}

// Global API instance
window.api = new ApiClient();
