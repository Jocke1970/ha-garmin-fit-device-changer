const CARD_VERSION = "0.1.0-m1.2";

const TEXT = {
  sv: {
    title: "FIT Device Patcher",
    profiles: "Enhetsprofiler",
    noProfiles: "Ingen enhetsprofil ännu. Importera först en äkta FIT-fil från en Garmin-enhet.",
    targetDevice: "Målenhet",
    makeDefault: "Gör till standard",
    remove: "Ta bort",
    referenceTitle: "Importera enhet från referens-FIT",
    referenceHelp: "Välj en äkta aktivitet som skapats av enheten. FIT-filen sparas inte; endast creator-identiteten lagras lokalt i Home Assistant.",
    referenceFile: "Referens-FIT",
    chooseFile: "Välj fil",
    noFileSelected: "Ingen fil vald",
    optionalName: "Visningsnamn (valfritt)",
    import: "Importera enhet",
    patchTitle: "Patcha FIT-fil",
    sourceFile: "FIT-fil att patcha",
    patch: "Patcha FIT",
    download: "Hämta patchad FIT",
    ready: "Klar",
    verified: "Övrig FIT-data verifierad oförändrad.",
    changed: "Ändrade creator-fält",
    importing: "Importerar referens-FIT…",
    patching: "Patchar och verifierar FIT…",
    imported: "Enhetsprofil importerad.",
    defaultSet: "Standardprofil uppdaterad.",
    deleted: "Enhetsprofil borttagen.",
    needReference: "Välj en referens-FIT först.",
    needSource: "Välj FIT-filen som ska patchas först.",
    needProfile: "Importera eller välj en målenhet först.",
    error: "Fel",
    serial: "Serial",
    software: "Programvara",
    product: "Product ID",
    default: "standard",
  },
  en: {
    title: "FIT Device Patcher",
    profiles: "Device profiles",
    noProfiles: "No device profile yet. First import a genuine FIT file from a Garmin device.",
    targetDevice: "Target device",
    makeDefault: "Make default",
    remove: "Remove",
    referenceTitle: "Import device from reference FIT",
    referenceHelp: "Choose a genuine activity created by the device. The FIT file is not stored; only the creator identity is saved locally in Home Assistant.",
    referenceFile: "Reference FIT",
    chooseFile: "Choose file",
    noFileSelected: "No file selected",
    optionalName: "Display name (optional)",
    import: "Import device",
    patchTitle: "Patch FIT file",
    sourceFile: "FIT file to patch",
    patch: "Patch FIT",
    download: "Download patched FIT",
    ready: "Ready",
    verified: "Other FIT data verified unchanged.",
    changed: "Changed creator fields",
    importing: "Importing reference FIT…",
    patching: "Patching and verifying FIT…",
    imported: "Device profile imported.",
    defaultSet: "Default profile updated.",
    deleted: "Device profile removed.",
    needReference: "Choose a reference FIT first.",
    needSource: "Choose the FIT file to patch first.",
    needProfile: "Import or select a target device first.",
    error: "Error",
    serial: "Serial",
    software: "Software",
    product: "Product ID",
    default: "default",
  },
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error || new Error("File read failed"));
    reader.onload = () => {
      const value = String(reader.result || "");
      const comma = value.indexOf(",");
      resolve(comma >= 0 ? value.slice(comma + 1) : value);
    };
    reader.readAsDataURL(file);
  });
}

function base64ToBlob(base64, type = "application/octet-stream") {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return new Blob([bytes], { type });
}

class FitDevicePatcherCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
    this._loaded = false;
    this._profiles = [];
    this._defaultProfileId = null;
    this._selectedProfileId = null;
    this._status = null;
    this._result = null;
    this._busy = false;
    this._downloadUrl = null;
    this._referenceFile = null;
    this._sourceFile = null;
    this._referenceLabel = "";
  }

  static getStubConfig() {
    return {};
  }

  setConfig(config) {
    this._config = config || {};
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._loaded) {
      this._loaded = true;
      this._loadProfiles();
    }
  }

  getCardSize() {
    return 7;
  }

  disconnectedCallback() {
    if (this._downloadUrl) URL.revokeObjectURL(this._downloadUrl);
  }

  _t() {
    const language = this._hass?.locale?.language || this._hass?.language || "en";
    return String(language).toLowerCase().startsWith("sv") ? TEXT.sv : TEXT.en;
  }

  async _loadProfiles() {
    if (!this._hass) return;
    try {
      const data = await this._hass.callApi("GET", "fit_device_patcher/profiles");
      this._applyProfiles(data);
    } catch (err) {
      this._setError(err);
    }
  }

  _applyProfiles(data) {
    this._profiles = Array.isArray(data?.profiles) ? data.profiles : [];
    this._defaultProfileId = data?.default_profile_id || null;
    const currentStillExists = this._profiles.some(
      (profile) => profile.profile_id === this._selectedProfileId
    );
    if (!currentStillExists) {
      this._selectedProfileId =
        this._defaultProfileId || this._profiles[0]?.profile_id || null;
    }
    this._render();
  }

  _selectedProfile() {
    return this._profiles.find(
      (profile) => profile.profile_id === this._selectedProfileId
    );
  }

  _setStatus(message, kind = "ok") {
    this._status = { message, kind };
    this._render();
  }

  _setError(err) {
    const t = this._t();
    const message = err?.message || err?.body?.error || String(err);
    this._status = { message: `${t.error}: ${message}`, kind: "error" };
    this._busy = false;
    this._render();
  }

  async _importProfile() {
    const t = this._t();
    const input = this.shadowRoot.querySelector("#reference-file");
    const file = this._referenceFile || input?.files?.[0];
    if (!file) {
      this._setStatus(t.needReference, "error");
      return;
    }

    const label = this.shadowRoot.querySelector("#reference-label")?.value ?? this._referenceLabel;
    this._referenceLabel = label;
    this._busy = true;
    this._setStatus(t.importing, "info");
    try {
      const contentBase64 = await fileToBase64(file);
      const data = await this._hass.callApi(
        "POST",
        "fit_device_patcher/profiles/import",
        { filename: file.name, content_base64: contentBase64, label }
      );
      this._applyProfiles(data);
      this._selectedProfileId = data?.profile?.profile_id || this._selectedProfileId;
      this._referenceFile = null;
      this._referenceLabel = "";
      this._busy = false;
      this._setStatus(t.imported, "ok");
    } catch (err) {
      this._setError(err);
    }
  }

  async _setDefault() {
    const t = this._t();
    if (!this._selectedProfileId) return;
    this._busy = true;
    this._render();
    try {
      const data = await this._hass.callApi(
        "POST",
        "fit_device_patcher/profiles/default",
        { profile_id: this._selectedProfileId }
      );
      this._busy = false;
      this._applyProfiles(data);
      this._setStatus(t.defaultSet, "ok");
    } catch (err) {
      this._setError(err);
    }
  }

  async _deleteProfile() {
    const t = this._t();
    if (!this._selectedProfileId) return;
    this._busy = true;
    this._render();
    try {
      const data = await this._hass.callApi(
        "POST",
        "fit_device_patcher/profiles/delete",
        { profile_id: this._selectedProfileId }
      );
      this._busy = false;
      this._applyProfiles(data);
      this._setStatus(t.deleted, "ok");
    } catch (err) {
      this._setError(err);
    }
  }

  async _patchFit() {
    const t = this._t();
    const file = this._sourceFile || this.shadowRoot.querySelector("#source-file")?.files?.[0];
    if (!file) {
      this._setStatus(t.needSource, "error");
      return;
    }
    if (!this._selectedProfileId) {
      this._setStatus(t.needProfile, "error");
      return;
    }

    this._busy = true;
    this._result = null;
    if (this._downloadUrl) {
      URL.revokeObjectURL(this._downloadUrl);
      this._downloadUrl = null;
    }
    this._setStatus(t.patching, "info");

    try {
      const contentBase64 = await fileToBase64(file);
      const data = await this._hass.callApi("POST", "fit_device_patcher/patch", {
        filename: file.name,
        content_base64: contentBase64,
        profile_id: this._selectedProfileId,
      });

      const blob = base64ToBlob(data.content_base64, "application/octet-stream");
      this._downloadUrl = URL.createObjectURL(blob);
      this._result = data;
      this._busy = false;
      this._setStatus(`${t.ready} — ${t.verified}`, "ok");
    } catch (err) {
      this._setError(err);
    }
  }

  _wireEvents() {
    const select = this.shadowRoot.querySelector("#profile-select");
    if (select) {
      select.addEventListener("change", (event) => {
        this._selectedProfileId = event.target.value || null;
        this._render();
      });
    }
    const referenceFile = this.shadowRoot.querySelector("#reference-file");
    if (referenceFile) {
      referenceFile.addEventListener("change", (event) => {
        this._referenceFile = event.target.files?.[0] || null;
        this._render();
      });
    }

    const referenceLabel = this.shadowRoot.querySelector("#reference-label");
    if (referenceLabel) {
      referenceLabel.addEventListener("input", (event) => {
        this._referenceLabel = event.target.value || "";
      });
    }

    const sourceFile = this.shadowRoot.querySelector("#source-file");
    if (sourceFile) {
      sourceFile.addEventListener("change", (event) => {
        this._sourceFile = event.target.files?.[0] || null;
        this._render();
      });
    }

    this.shadowRoot.querySelector("#import-button")?.addEventListener("click", () => this._importProfile());
    this.shadowRoot.querySelector("#default-button")?.addEventListener("click", () => this._setDefault());
    this.shadowRoot.querySelector("#delete-button")?.addEventListener("click", () => this._deleteProfile());
    this.shadowRoot.querySelector("#patch-button")?.addEventListener("click", () => this._patchFit());
  }

  _render() {
    if (!this.shadowRoot) return;
    const t = this._t();
    const selected = this._selectedProfile();
    const options = this._profiles
      .map(
        (profile) => `<option value="${escapeHtml(profile.profile_id)}" ${
          profile.profile_id === this._selectedProfileId ? "selected" : ""
        }>${escapeHtml(profile.label)}${profile.is_default ? ` (${t.default})` : ""}</option>`
      )
      .join("");

    const changes = this._result?.changes || [];
    const changesHtml = changes.length
      ? `<div class="changes"><strong>${t.changed}</strong>${changes
          .map(
            (change) => `<div class="change"><code>${escapeHtml(change.message)}.${escapeHtml(
              change.field
            )}</code><span>${escapeHtml(change.old)} → ${escapeHtml(change.new)}</span></div>`
          )
          .join("")}</div>`
      : "";

    const resultHtml = this._result && this._downloadUrl
      ? `<div class="result">
          ${changesHtml}
          <a class="primary download" href="${this._downloadUrl}" download="${escapeHtml(
            this._result.filename
          )}">${t.download}</a>
        </div>`
      : "";

    const statusHtml = this._status
      ? `<div class="status ${escapeHtml(this._status.kind)}">${escapeHtml(this._status.message)}</div>`
      : "";

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { padding: 18px; }
        h2 { margin: 0 0 18px; font-size: 1.35rem; font-weight: 500; }
        h3 { margin: 0 0 8px; font-size: 1rem; }
        .section { padding: 14px 0; border-top: 1px solid var(--divider-color); }
        .section:first-of-type { border-top: 0; padding-top: 0; }
        .help, .meta { color: var(--secondary-text-color); font-size: 0.9rem; line-height: 1.4; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px; }
        .full { grid-column: 1 / -1; }
        label { display: flex; flex-direction: column; gap: 6px; font-size: 0.9rem; }
        input[type="text"], select { box-sizing: border-box; width: 100%; padding: 10px; border: 1px solid var(--divider-color); border-radius: 8px; background: var(--card-background-color); color: var(--primary-text-color); }
        .file-field { display: flex; flex-direction: column; gap: 6px; font-size: 0.9rem; min-width: 0; }
        .file-picker { display: flex; align-items: stretch; min-width: 0; border: 1px solid var(--divider-color); border-radius: 8px; overflow: hidden; background: var(--card-background-color); }
        .file-input { position: absolute; inline-size: 1px; block-size: 1px; opacity: 0; pointer-events: none; }
        .file-button { flex: 0 0 auto; justify-content: center; padding: 10px 12px; background: var(--secondary-background-color); border-right: 1px solid var(--divider-color); cursor: pointer; font-size: 0.9rem; white-space: nowrap; }
        .file-name { flex: 1 1 auto; min-width: 0; padding: 10px 12px; color: var(--primary-text-color); overflow-wrap: anywhere; word-break: break-word; line-height: 1.25; }
        .file-name.empty { color: var(--secondary-text-color); }
        .actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
        button, a.primary { border: 0; border-radius: 8px; padding: 10px 14px; cursor: pointer; font: inherit; text-decoration: none; }
        button.primary, a.primary { background: var(--primary-color); color: var(--text-primary-color, white); }
        button.secondary { background: var(--secondary-background-color); color: var(--primary-text-color); }
        button.danger { background: var(--error-color); color: white; }
        button:disabled { opacity: 0.5; cursor: default; }
        .profile-meta { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 12px; }
        .status { margin: 12px 0 0; padding: 10px 12px; border-radius: 8px; background: var(--secondary-background-color); }
        .status.error { border-left: 4px solid var(--error-color); }
        .status.ok { border-left: 4px solid var(--success-color, #43a047); }
        .status.info { border-left: 4px solid var(--primary-color); }
        .changes { margin-top: 12px; }
        .change { display: flex; justify-content: space-between; gap: 12px; padding: 5px 0; font-size: 0.9rem; }
        .download { display: inline-block; margin-top: 14px; }
        @media (max-width: 600px) { .grid { grid-template-columns: 1fr; } }
      </style>
      <ha-card>
        <h2>${escapeHtml(this._config.title || t.title)}</h2>

        <div class="section">
          <h3>${t.profiles}</h3>
          ${
            this._profiles.length
              ? `<label>${t.targetDevice}<select id="profile-select">${options}</select></label>
                 ${selected ? `<div class="profile-meta meta">
                   <span>${t.product}: ${escapeHtml(selected.product)}</span>
                   <span>${t.serial}: ${escapeHtml(selected.serial_number)}</span>
                   <span>${t.software}: ${escapeHtml(selected.software_version)}</span>
                 </div>` : ""}
                 <div class="actions">
                   <button id="default-button" class="secondary" ${this._busy || selected?.is_default ? "disabled" : ""}>${t.makeDefault}</button>
                   <button id="delete-button" class="danger" ${this._busy ? "disabled" : ""}>${t.remove}</button>
                 </div>`
              : `<div class="help">${t.noProfiles}</div>`
          }
        </div>

        <div class="section">
          <h3>${t.referenceTitle}</h3>
          <div class="help">${t.referenceHelp}</div>
          <div class="grid">
            <div class="file-field">
              <span>${t.referenceFile}</span>
              <div class="file-picker">
                <input id="reference-file" class="file-input" type="file" accept=".fit,application/octet-stream">
                <label class="file-button" for="reference-file">${t.chooseFile}</label>
                <div class="file-name ${this._referenceFile ? "" : "empty"}" title="${escapeHtml(this._referenceFile?.name || "")}">${escapeHtml(this._referenceFile?.name || t.noFileSelected)}</div>
              </div>
            </div>
            <label>${t.optionalName}<input id="reference-label" type="text" value="${escapeHtml(this._referenceLabel)}"></label>
          </div>
          <div class="actions"><button id="import-button" class="primary" ${this._busy ? "disabled" : ""}>${t.import}</button></div>
        </div>

        <div class="section">
          <h3>${t.patchTitle}</h3>
          <div class="file-field">
            <span>${t.sourceFile}</span>
            <div class="file-picker">
              <input id="source-file" class="file-input" type="file" accept=".fit,application/octet-stream">
              <label class="file-button" for="source-file">${t.chooseFile}</label>
              <div class="file-name ${this._sourceFile ? "" : "empty"}" title="${escapeHtml(this._sourceFile?.name || "")}">${escapeHtml(this._sourceFile?.name || t.noFileSelected)}</div>
            </div>
          </div>
          <div class="actions"><button id="patch-button" class="primary" ${this._busy || !this._profiles.length ? "disabled" : ""}>${t.patch}</button></div>
          ${resultHtml}
        </div>
        ${statusHtml}
        <div class="meta" style="margin-top: 12px">v${CARD_VERSION}</div>
      </ha-card>
    `;
    this._wireEvents();
  }
}

customElements.define("fit-device-patcher-card", FitDevicePatcherCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "fit-device-patcher-card",
  name: "FIT Device Patcher",
  description: "Patch the creator Garmin device identity in FIT activity files.",
});

console.info(`%c FIT Device Patcher %c v${CARD_VERSION} `, "background:#03a9f4;color:white", "background:#222;color:white");
