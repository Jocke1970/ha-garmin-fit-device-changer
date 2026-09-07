const CARD_VERSION = "0.1.0-m1.9";

const TEXT = {
  sv: {
    title: "Garmin FIT Device Changer", profiles: "Enhetsprofiler", target: "Målenhet",
    noProfiles: "Ingen profil ännu. Importera en referens-FIT eller lägg till en Garmin-enhet manuellt.",
    product: "Product ID", serial: "Serial", software: "Programvara", profileType: "Profiltyp",
    full: "Full identitet", basic: "Grunddata", makeDefault: "Gör till standard", remove: "Ta bort",
    addTitle: "Lägg till enhet", addHelp: "Välj hur enheten ska läggas till.", refTab: "Referens-FIT", recommended: "Rekommenderad", manualTab: "Manuell profil",
    refTitle: "Referens-FIT", refHelp: "Rekommenderat: välj en äkta aktivitet från enheten. FIT-filen sparas inte.",
    refFile: "Referens-FIT", choose: "Välj fil", noFile: "Ingen fil vald", optionalName: "Visningsnamn (valfritt)", import: "Importera enhet",
    manualTitle: "Lägg till enhet manuellt", manualHelp: "Saknar du en referensaktivitet kan profilen skapas från Garmins modell-/Product ID-data.",
    model: "Garmin-modell", otherModel: "Annan Garmin-modell…", modelName: "Modellnamn", customProduct: "Product ID",
    customHelp: "För en modell som ännu inte finns i listan: ange modellnamn och Garmin FIT Product ID.",
    identity: "Identitet", fullMode: "Full identitet (serienummer + firmware)", basicMode: "Endast Garmin grunddata",
    fullHelp: "Full identitet ersätter även serienummer och firmware. Det är metoden vi har verifierat mot Garmin Connect.",
    basicHelp: "Grunddata ändrar endast Garmin manufacturer + Product ID. Serienummer och firmware i källfilen lämnas helt orörda. Garmin Connect kan därför känna igen modellen men behöver inte koppla aktiviteten till en fysisk Garmin-enhet.",
    serialNumber: "Serienummer", firmware: "Firmwareversion", saveManual: "Spara manuell profil",
    patchTitle: "Patcha FIT-fil", sourceFile: "FIT-fil att patcha", patch: "Patcha FIT", download: "Hämta patchad FIT",
    changed: "Ändrade creator-fält", verified: "Övrig FIT-data verifierad oförändrad.", ready: "Klar",
    importing: "Importerar referens-FIT…", imported: "Enhetsprofil importerad.", saving: "Sparar manuell enhetsprofil…", saved: "Manuell enhetsprofil sparad.",
    patching: "Patchar och verifierar FIT…", defaultSet: "Standardprofil uppdaterad.", deleted: "Enhetsprofil borttagen.", error: "Fel"
  },
  en: {
    title: "Garmin FIT Device Changer", profiles: "Device profiles", target: "Target device",
    noProfiles: "No profile yet. Import a reference FIT or add a Garmin device manually.",
    product: "Product ID", serial: "Serial", software: "Software", profileType: "Profile type",
    full: "Full identity", basic: "Basic data", makeDefault: "Make default", remove: "Remove",
    addTitle: "Add device", addHelp: "Choose how the device should be added.", refTab: "Reference FIT", recommended: "Recommended", manualTab: "Manual profile",
    refTitle: "Reference FIT", refHelp: "Recommended: choose a genuine activity from the device. The FIT file is not stored.",
    refFile: "Reference FIT", choose: "Choose file", noFile: "No file selected", optionalName: "Display name (optional)", import: "Import device",
    manualTitle: "Add device manually", manualHelp: "If you do not have a reference activity, create a profile from Garmin model/Product ID data.",
    model: "Garmin model", otherModel: "Other Garmin model…", modelName: "Model name", customProduct: "Product ID",
    customHelp: "For a model that is not in the list yet, enter its model name and Garmin FIT Product ID.",
    identity: "Identity", fullMode: "Full identity (serial + firmware)", basicMode: "Garmin basic data only",
    fullHelp: "Full identity also replaces serial number and firmware. This is the method verified against Garmin Connect.",
    basicHelp: "Basic mode changes only Garmin manufacturer + Product ID. Source serial/firmware stay completely unchanged. Garmin Connect may recognize the model without linking the activity to a physical Garmin device.",
    serialNumber: "Serial number", firmware: "Firmware version", saveManual: "Save manual profile",
    patchTitle: "Patch FIT file", sourceFile: "FIT file to patch", patch: "Patch FIT", download: "Download patched FIT",
    changed: "Changed creator fields", verified: "Other FIT data verified unchanged.", ready: "Ready",
    importing: "Importing reference FIT…", imported: "Device profile imported.", saving: "Saving manual device profile…", saved: "Manual device profile saved.",
    patching: "Patching and verifying FIT…", defaultSet: "Default profile updated.", deleted: "Device profile removed.", error: "Error"
  }
};

const esc = (v) => String(v ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
const to64 = (file) => new Promise((resolve, reject) => {
  const r = new FileReader();
  r.onerror = () => reject(r.error || new Error("File read failed"));
  r.onload = () => resolve(String(r.result || "").split(",").pop());
  r.readAsDataURL(file);
});
const from64 = (value) => {
  const b = atob(value), a = new Uint8Array(b.length);
  for (let i = 0; i < b.length; i++) a[i] = b.charCodeAt(i);
  return new Blob([a], { type: "application/octet-stream" });
};

class GarminFitDeviceChangerCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {}; this._hass = null; this._loaded = false; this._busy = false;
    this._profiles = []; this._catalog = []; this._selected = null; this._downloadUrl = null; this._result = null; this._status = null;
    this._refFile = null; this._sourceFile = null; this._refLabel = "";
    this._manual = { device: "", mode: "full", serial: "", firmware: "", label: "", modelName: "", product: "" };
    this._open = { profiles: false, add: false, patch: false };
    this._addMode = "reference";
  }

  static getStubConfig() { return {}; }
  setConfig(config) { this._config = config || {}; this._render(); }
  set hass(hass) { this._hass = hass; if (!this._loaded) { this._loaded = true; this._load(); } }
  getCardSize() { return 7; }
  disconnectedCallback() { if (this._downloadUrl) URL.revokeObjectURL(this._downloadUrl); }
  _t() { const l = this._hass?.locale?.language || this._hass?.language || "en"; return String(l).toLowerCase().startsWith("sv") ? TEXT.sv : TEXT.en; }
  _pickProfile() { return this._profiles.find((p) => p.profile_id === this._selected); }
  _setStatus(message, kind = "ok") { this._status = { message, kind }; this._render(); }
  _error(err) { const t = this._t(); this._busy = false; this._status = { message: `${t.error}: ${err?.body?.error || err?.message || err}`, kind: "error" }; this._render(); }

  _apply(data) {
    this._profiles = Array.isArray(data?.profiles) ? data.profiles : [];
    if (Array.isArray(data?.device_catalog)) this._catalog = data.device_catalog;
    if (!this._manual.device || (this._manual.device !== "custom" && !this._catalog.some((d) => d.key === this._manual.device))) {
      this._manual.device = this._catalog.find((d) => d.key === "fenix_7_pro")?.key || this._catalog[0]?.key || "custom";
    }
    if (!this._profiles.some((p) => p.profile_id === this._selected)) this._selected = data?.default_profile_id || this._profiles[0]?.profile_id || null;
    this._render();
  }

  async _load() {
    try { this._apply(await this._hass.callApi("GET", "garmin_fit_device_changer/profiles")); }
    catch (e) { this._error(e); }
  }

  async _importRef() {
    const t = this._t();
    if (!this._refFile) return this._setStatus(`${t.error}: ${t.refFile}`, "error");
    this._busy = true; this._setStatus(t.importing, "info");
    try {
      const data = await this._hass.callApi("POST", "garmin_fit_device_changer/profiles/import", {
        filename: this._refFile.name, content_base64: await to64(this._refFile), label: this._refLabel
      });
      this._refFile = null; this._refLabel = ""; this._busy = false; this._selected = data.profile?.profile_id || this._selected; this._apply(data); this._setStatus(t.imported);
    } catch (e) { this._error(e); }
  }

  async _saveManual() {
    const t = this._t();
    this._busy = true; this._setStatus(t.saving, "info");
    try {
      const body = { device_key: this._manual.device, identity_mode: this._manual.mode, label: this._manual.label };
      if (this._manual.device === "custom") { body.model_name = this._manual.modelName; body.product_id = this._manual.product; }
      if (this._manual.mode === "full") { body.serial_number = this._manual.serial; body.software_version = this._manual.firmware; }
      const data = await this._hass.callApi("POST", "garmin_fit_device_changer/profiles/manual", body);
      this._manual.serial = ""; this._manual.firmware = ""; this._manual.label = ""; this._manual.modelName = ""; this._manual.product = ""; this._busy = false; this._selected = data.profile?.profile_id || this._selected; this._apply(data); this._setStatus(t.saved);
    } catch (e) { this._error(e); }
  }

  async _profileAction(path, okText) {
    if (!this._selected) return;
    this._busy = true; this._render();
    try { this._busy = false; this._apply(await this._hass.callApi("POST", `garmin_fit_device_changer/profiles/${path}`, { profile_id: this._selected })); this._setStatus(okText); }
    catch (e) { this._error(e); }
  }

  async _patch() {
    const t = this._t();
    if (!this._sourceFile) return this._setStatus(`${t.error}: ${t.sourceFile}`, "error");
    if (!this._selected) return this._setStatus(`${t.error}: ${t.target}`, "error");
    this._busy = true; this._result = null; if (this._downloadUrl) URL.revokeObjectURL(this._downloadUrl); this._downloadUrl = null; this._setStatus(t.patching, "info");
    try {
      const data = await this._hass.callApi("POST", "garmin_fit_device_changer/patch", {
        filename: this._sourceFile.name, content_base64: await to64(this._sourceFile), profile_id: this._selected
      });
      this._downloadUrl = URL.createObjectURL(from64(data.content_base64)); this._result = data; this._busy = false; this._setStatus(`${t.ready} — ${t.verified}`);
    } catch (e) { this._error(e); }
  }

  _wire() {
    const q = (s) => this.shadowRoot.querySelector(s);
    q("#profile")?.addEventListener("change", (e) => { this._selected = e.target.value || null; this._render(); });
    q("#ref-file")?.addEventListener("change", (e) => { this._refFile = e.target.files?.[0] || null; this._render(); });
    q("#src-file")?.addEventListener("change", (e) => { this._sourceFile = e.target.files?.[0] || null; this._render(); });
    q("#ref-label")?.addEventListener("input", (e) => { this._refLabel = e.target.value || ""; });
    q("#manual-device")?.addEventListener("change", (e) => { this._manual.device = e.target.value || ""; this._render(); });
    q("#manual-mode")?.addEventListener("change", (e) => { this._manual.mode = e.target.value || "full"; this._render(); });
    [["#manual-serial","serial"],["#manual-firmware","firmware"],["#manual-label","label"],["#manual-model-name","modelName"],["#manual-product","product"]].forEach(([s,k]) => q(s)?.addEventListener("input", (e) => { this._manual[k] = e.target.value || ""; }));
    q("#import")?.addEventListener("click", () => this._importRef()); q("#manual-save")?.addEventListener("click", () => this._saveManual());
    q("#default")?.addEventListener("click", () => this._profileAction("default", this._t().defaultSet)); q("#delete")?.addEventListener("click", () => this._profileAction("delete", this._t().deleted));
    q("#patch")?.addEventListener("click", () => this._patch());
    [["#details-profiles","profiles"],["#details-add","add"],["#details-patch","patch"]].forEach(([selector,key]) => {
      q(selector)?.addEventListener("toggle", (event) => { this._open[key] = event.target.open; });
    });
    q("#add-reference")?.addEventListener("click", () => { this._addMode = "reference"; this._render(); });
    q("#add-manual")?.addEventListener("click", () => { this._addMode = "manual"; this._render(); });
  }

  _filePicker(id, title, file) {
    const t = this._t(); return `<div class="field"><span>${title}</span><div class="picker"><input id="${id}" type="file" accept=".fit,application/octet-stream"><label for="${id}">${t.choose}</label><div class="fname ${file ? "" : "empty"}">${esc(file?.name || t.noFile)}</div></div></div>`;
  }

  _render() {
    if (!this.shadowRoot) return;
    const t = this._t(), selected = this._pickProfile(), manualDevice = this._catalog.find((d) => d.key === this._manual.device), isCustom = this._manual.device === "custom";
    const profiles = this._profiles.map((p) => `<option value="${esc(p.profile_id)}" ${p.profile_id === this._selected ? "selected" : ""}>${esc(p.label)}${p.is_default ? " (standard)" : ""}</option>`).join("");
    const devices = this._catalog.map((d) => `<option value="${esc(d.key)}" ${d.key === this._manual.device ? "selected" : ""}>${esc(d.label)} — ${d.product}</option>`).join("") + `<option value="custom" ${isCustom ? "selected" : ""}>${t.otherModel}</option>`;
    const customFields = isCustom ? `<label>${t.modelName}<input id="manual-model-name" type="text" value="${esc(this._manual.modelName)}" placeholder="Garmin Edge 850"></label><label>${t.customProduct}<input id="manual-product" type="text" inputmode="numeric" value="${esc(this._manual.product)}" placeholder="4634"></label><div class="help full">${t.customHelp}</div>` : "";
    const manualPlaceholder = isCustom ? this._manual.modelName : (manualDevice?.label || "");
    const changes = (this._result?.changes || []).map((c) => `<div class="change"><code>${esc(c.message)}.${esc(c.field)}</code><span>${esc(c.old)} → ${esc(c.new)}</span></div>`).join("");
    const result = this._result && this._downloadUrl ? `<div class="result"><strong>${t.changed}</strong>${changes}<a class="primary download" href="${this._downloadUrl}" download="${esc(this._result.filename)}">${t.download}</a></div>` : "";
    const status = this._status ? `<div class="status ${esc(this._status.kind)}">${esc(this._status.message)}</div>` : "";
    const icon = (name) => `<ha-icon icon="${name}" class="section-icon"></ha-icon>`;
    const chevron = '<span class="chevron" aria-hidden="true"></span>';
    const configuredTitle = String(this._config?.title || "").trim();
    const oldTitle = configuredTitle.toLowerCase() === "fit device patcher";
    const displayTitle = oldTitle || !configuredTitle ? t.title : configuredTitle;

    this.shadowRoot.innerHTML = `<style>
      :host{display:block}
      ha-card{padding:16px 18px 14px;overflow:hidden}
      .brand{position:relative;margin:0 0 10px;padding:11px 14px 10px;border:1px solid var(--divider-color);border-radius:12px;background:linear-gradient(110deg,var(--secondary-background-color),var(--card-background-color));overflow:hidden}
      .brand:before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--primary-color)}
      .brand-kicker,.brand-sub{font-size:.66rem;letter-spacing:.21em;text-transform:uppercase;font-weight:650;color:var(--secondary-text-color)}
      .brand-title{font-size:1.25rem;line-height:1.05;letter-spacing:.08em;text-transform:uppercase;font-weight:800;margin:4px 0 3px;color:var(--primary-text-color)}
      .section{padding:0;border-top:1px solid var(--divider-color)}
      .section:first-of-type{border-top:0}
      .section summary{display:flex;align-items:center;gap:9px;min-height:24px;padding:13px 3px;cursor:pointer;font-size:.98rem;font-weight:550;user-select:none;list-style:none;border-radius:8px}
      .section summary::-webkit-details-marker{display:none}
      .section summary::marker{content:""}
      .section summary:focus{outline:none}
      .section summary:focus-visible{outline:2px solid var(--primary-color);outline-offset:-2px}
      .section summary:hover{background:var(--secondary-background-color)}
      .chevron{width:7px;height:7px;flex:0 0 7px;border-right:2px solid currentColor;border-bottom:2px solid currentColor;transform:rotate(-45deg);transition:transform .16s ease;color:var(--secondary-text-color);margin-left:2px;position:relative;left:4px}
      details[open]>summary .chevron{transform:rotate(45deg);color:var(--primary-color)}
      .section-icon{--mdc-icon-size:19px;color:var(--secondary-text-color)}
      details[open]>summary .section-icon{color:var(--primary-color)}
      .summary-title{white-space:nowrap}
      .summary-meta{margin-left:auto;color:var(--secondary-text-color);font-size:.82rem;font-weight:400;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:48%}
      .section-body{padding:0 6px 16px 24px}
      .method-switch{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin:10px 0 13px}
      .method-tab{display:flex;align-items:center;justify-content:center;gap:8px;min-height:44px;border:1px solid var(--divider-color);border-radius:9px;background:var(--card-background-color);color:var(--primary-text-color);font:inherit;cursor:pointer}
      .method-tab.active{border:2px solid var(--primary-color);background:color-mix(in srgb,var(--primary-color) 8%,var(--card-background-color));padding:8px 11px}
      .method-tab .section-icon{--mdc-icon-size:18px}
      .recommended{display:inline-block;margin-left:4px;font-size:.72rem;color:var(--secondary-text-color);font-weight:400}
      .method-heading{font-weight:650;margin:3px 0 7px}
      .help,.meta{color:var(--secondary-text-color);font-size:.85rem;line-height:1.4}
      .grid{display:grid;grid-template-columns:1fr 1fr;gap:11px;margin-top:10px}
      .full{grid-column:1/-1}
      .field,label{display:flex;flex-direction:column;gap:5px;font-size:.85rem}
      input[type=text],select{box-sizing:border-box;width:100%;min-height:40px;padding:9px 10px;border:1px solid var(--divider-color);border-radius:8px;background:var(--card-background-color);color:var(--primary-text-color);font:inherit}
      .picker{display:flex;min-height:40px;border:1px solid var(--divider-color);border-radius:8px;overflow:hidden}
      .picker input{position:absolute;width:1px;height:1px;opacity:0}
      .picker label{justify-content:center;padding:9px 12px;background:var(--secondary-background-color);border-right:1px solid var(--divider-color);cursor:pointer;white-space:nowrap}
      .fname{display:flex;align-items:center;padding:8px 11px;overflow-wrap:anywhere;min-width:0}
      .fname.empty{color:var(--secondary-text-color)}
      .actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:11px}
      button,a.primary{border:0;border-radius:8px;padding:9px 13px;font:inherit;text-decoration:none;cursor:pointer}
      button.primary,a.primary{background:var(--primary-color);color:var(--text-primary-color,#fff)}
      button.secondary{background:var(--secondary-background-color);color:var(--primary-text-color)}
      button.danger{background:var(--error-color);color:#fff}
      button:disabled{opacity:.5}
      .profile-meta{display:flex;gap:10px;flex-wrap:wrap;margin-top:7px}
      .note,.status{margin-top:11px;padding:9px 11px;border-radius:8px;background:var(--secondary-background-color);font-size:.85rem;line-height:1.4}
      .note.full,.status.ok{border-left:4px solid var(--success-color,#43a047)}
      .note.basic{border-left:4px solid var(--warning-color,#ff9800)}
      .status.error{border-left:4px solid var(--error-color)}
      .status.info{border-left:4px solid var(--primary-color)}
      .change{display:flex;justify-content:space-between;gap:12px;padding:5px 0;font-size:.85rem}
      .download{display:inline-block;margin-top:12px}
      .version{margin:10px 2px 0;font-size:.76rem}
      @media(max-width:600px){ha-card{padding:14px}.brand{padding:10px 12px}.brand-title{font-size:1.08rem}.grid{grid-template-columns:1fr}.section-body{padding-left:20px}.summary-meta{max-width:40%}.method-switch{grid-template-columns:1fr}}
    </style><ha-card>
      <div class="brand" aria-label="${esc(displayTitle)}"><div class="brand-kicker">GARMIN FIT</div><div class="brand-title">DEVICE CHANGER</div><div class="brand-sub">HOME ASSISTANT</div></div>
      <details id="details-profiles" class="section" ${this._open.profiles ? "open" : ""}><summary>${chevron}${icon("mdi:devices")}<span class="summary-title">${t.profiles}</span>${selected ? `<span class="summary-meta">${esc(selected.label)}</span>` : ""}</summary><div class="section-body">${this._profiles.length ? `<label>${t.target}<select id="profile">${profiles}</select></label>${selected ? `<div class="profile-meta meta"><span>${t.product}: ${selected.product}</span><span>${t.serial}: ${esc(selected.serial_number)}</span><span>${t.software}: ${esc(selected.software_version)}</span><span>${t.profileType}: ${selected.identity_mode === "full" ? t.full : t.basic}</span></div>` : ""}<div class="actions"><button id="default" class="secondary" ${this._busy || selected?.is_default ? "disabled" : ""}>${t.makeDefault}</button><button id="delete" class="danger" ${this._busy ? "disabled" : ""}>${t.remove}</button></div>` : `<div class="help">${t.noProfiles}</div>`}</div></details>
      <details id="details-add" class="section" ${this._open.add ? "open" : ""}><summary>${chevron}${icon("mdi:plus-circle-outline")}<span class="summary-title">${t.addTitle}</span></summary><div class="section-body"><div class="help">${t.addHelp}</div><div class="method-switch"><button id="add-reference" class="method-tab ${this._addMode === "reference" ? "active" : ""}" type="button">${icon("mdi:file-check-outline")}<span>${t.refTab}<span class="recommended">${t.recommended}</span></span></button><button id="add-manual" class="method-tab ${this._addMode === "manual" ? "active" : ""}" type="button">${icon("mdi:form-textbox")}<span>${t.manualTab}</span></button></div>${this._addMode === "reference" ? `<div class="method-heading">${t.refTitle}</div><div class="help">${t.refHelp}</div><div class="grid">${this._filePicker("ref-file",t.refFile,this._refFile)}<label>${t.optionalName}<input id="ref-label" type="text" value="${esc(this._refLabel)}"></label></div><div class="actions"><button id="import" class="primary" ${this._busy ? "disabled" : ""}>${t.import}</button></div>` : `<div class="method-heading">${t.manualTitle}</div><div class="help">${t.manualHelp}</div><div class="grid"><label>${t.model}<select id="manual-device">${devices}</select></label><label>${t.identity}<select id="manual-mode"><option value="full" ${this._manual.mode === "full" ? "selected" : ""}>${t.fullMode}</option><option value="basic" ${this._manual.mode === "basic" ? "selected" : ""}>${t.basicMode}</option></select></label>${customFields}${this._manual.mode === "full" ? `<label>${t.serialNumber}<input id="manual-serial" type="text" inputmode="numeric" value="${esc(this._manual.serial)}"></label><label>${t.firmware}<input id="manual-firmware" type="text" inputmode="decimal" value="${esc(this._manual.firmware)}" placeholder="30.11"></label>` : ""}<label class="full">${t.optionalName}<input id="manual-label" type="text" value="${esc(this._manual.label)}" placeholder="${esc(manualPlaceholder)}"></label></div><div class="note ${this._manual.mode}">${this._manual.mode === "full" ? t.fullHelp : t.basicHelp}</div><div class="actions"><button id="manual-save" class="primary" ${this._busy ? "disabled" : ""}>${t.saveManual}</button></div>`}</div></details>
      <details id="details-patch" class="section" ${this._open.patch ? "open" : ""}><summary>${chevron}${icon("mdi:file-edit-outline")}<span class="summary-title">${t.patchTitle}</span>${this._sourceFile ? `<span class="summary-meta">${esc(this._sourceFile.name)}</span>` : ""}</summary><div class="section-body">${this._filePicker("src-file",t.sourceFile,this._sourceFile)}<div class="actions"><button id="patch" class="primary" ${this._busy || !this._profiles.length ? "disabled" : ""}>${t.patch}</button></div>${result}</div></details>${status}<div class="meta version">v${CARD_VERSION}</div>
    </ha-card>`;
    this._wire();
  }
}

customElements.define("garmin-fit-device-changer-card", GarminFitDeviceChangerCard);
if (!customElements.get("fit-device-patcher-card")) {
  customElements.define("fit-device-patcher-card", class extends GarminFitDeviceChangerCard {});
}
window.customCards = window.customCards || [];
window.customCards.push({ type: "garmin-fit-device-changer-card", name: "Garmin FIT Device Changer", description: "Patch the creator Garmin device identity in FIT activity files." });
console.info(`%c Garmin FIT Device Changer %c v${CARD_VERSION} `, "background:#03a9f4;color:white", "background:#222;color:white");