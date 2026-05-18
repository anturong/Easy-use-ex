import { app } from "../../scripts/app.js";

const STYLE_HREF = "extensions/Easy-use-ex/style.css";
const PALETTE = ["#f59e0b", "#10b981", "#3b82f6", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6", "#f97316", "#06b6d4", "#84cc16"];
const INVALID_FILE_CHARS = /[\\/:*?"<>|]/g;

function ensureStyleLoaded() {
    if (document.querySelector(`link[href="${STYLE_HREF}"]`)) return;
    const style = document.createElement("link");
    style.rel = "stylesheet";
    style.href = STYLE_HREF;
    document.head.appendChild(style);
}

function esc(value) {
    const div = document.createElement("div");
    div.textContent = String(value ?? "");
    return div.innerHTML;
}

function escAttr(value) {
    return String(value ?? "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/'/g, "&#39;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function summarizePreview(text) {
    const normalized = String(text || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n").trim();
    if (!normalized) return "暂无字幕内容";
    return normalized.split("\n").filter((line) => line.trim()).slice(0, 6).join("\n");
}

function parseCharacter(rawText) {
    const patterns = [/^\s*\[([^\]]+)\]\s*([\s\S]*)/, /^\s*\(([^)]+)\)\s*([\s\S]*)/, /^\s*([^:\n]{1,20})[:：]\s*([\s\S]*)/];
    for (const pattern of patterns) {
        const match = rawText.match(pattern);
        if (match && match[1].trim()) return { character: match[1].trim(), text: match[2].trim() };
    }
    return null;
}

function parseSrt(text) {
    const normalized = String(text || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n").replace(/^\uFEFF/, "").trim();
    if (!normalized) return [];
    const blocks = normalized.split(/\n\s*\n/);
    const result = [];
    for (const block of blocks) {
        const lines = block.trim().split("\n");
        if (lines.length < 2) continue;
        let cursor = 0;
        let index = result.length + 1;
        if (/^\d+$/.test(lines[0].trim())) {
            index = parseInt(lines[0].trim(), 10);
            cursor = 1;
        }
        const tm = lines[cursor]?.trim().match(/(\d{1,2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,.]\d{3})/);
        if (!tm) continue;
        const rawText = lines.slice(cursor + 1).join("\n").trim();
        const parsed = parseCharacter(rawText);
        result.push({
            index,
            startRaw: tm[1],
            endRaw: tm[2],
            start: tm[1].replace(",", "."),
            end: tm[2].replace(",", "."),
            character: parsed ? parsed.character : "",
            text: parsed ? parsed.text : rawText,
            rawText,
        });
    }
    return result;
}

function buildSrt(subs) {
    return subs.map((s) => `${s.index}\n${s.startRaw} --> ${s.endRaw}\n${s.character ? `[${s.character}] ${s.text}` : s.text}`).join("\n\n");
}

function nextColor(chars) {
    return PALETTE[chars.length % PALETTE.length];
}

function ensureChar(chars, name) {
    if (!name?.trim()) return chars;
    const trimmed = name.trim();
    if (chars.some((c) => c.name === trimmed)) return chars;
    return [...chars, { name: trimmed, color: nextColor(chars) }];
}

function cloneState(state) {
    return {
        sourceText: state?.sourceText || "",
        fileName: state?.fileName || "",
        subtitles: (state?.subtitles || []).map((s) => ({ ...s })),
        chars: (state?.chars || []).map((c) => ({ ...c })),
    };
}

function getNodeState(node) {
    node.__easyuseSubcastState ||= { sourceText: "", fileName: "", subtitles: [], chars: [], openSnapshot: null };
    return node.__easyuseSubcastState;
}

function setNodeState(node, patch) {
    node.__easyuseSubcastState = { ...getNodeState(node), ...patch };
    updatePreview(node);
}

function updatePreview(node) {
    if (!node?.__easyuseSubcastPreviewEl) return;
    node.__easyuseSubcastPreviewEl.textContent = summarizePreview(getNodeState(node).sourceText);
}

class SubCastDialog {
    constructor() {
        ensureStyleLoaded();
        this.node = null;
        this.textWidget = null;
        this.overlay = null;
        this.fileInput = null;
        this.fileName = "";
        this.subs = [];
        this.chars = [];
        this.selectedSet = new Set();
        this.editing = -1;
        this.lastClick = -1;
        this._buildDom();
    }

    _buildDom() {
        this.overlay = document.createElement("div");
        this.overlay.className = "sc-overlay";
        this.overlay.style.display = "none";
        this.overlay.tabIndex = 0;
        this.overlay.innerHTML = `
            <div class="sc-dialog">
                <div class="sc-topbar">
                    <span class="sc-brand">SubCast SRT Editor</span>
                    <span class="sc-filename" id="sc-filename"></span>
                    <div style="flex:1"></div>
                    <button class="sc-topbar-btn" id="sc-btn-reset">重置字幕</button>
                    <button class="sc-topbar-btn sc-topbar-save" id="sc-btn-save">保存到节点</button>
                    <button class="sc-topbar-btn sc-topbar-close" id="sc-btn-close">×</button>
                </div>
                <div class="sc-toolbar">
                    <button class="sc-tb" id="sc-tb-open">打开文件</button>
                    <button class="sc-tb" id="sc-tb-save-file">下载SRT</button>
                    <div class="sc-tdiv"></div>
                    <button class="sc-tb sc-tb-primary" id="sc-tb-export">导出 ZIP</button>
                </div>
                <div class="sc-main">
                    <aside class="sc-cpanel" id="sc-cpanel">
                        <div class="sc-cpanel-hdr"><span class="sc-cpanel-title">角色列表 (双击重命名)</span></div>
                        <div class="sc-cadd">
                            <input class="sc-cadd-input" id="sc-add-char" placeholder="新增角色名，回车添加">
                            <div class="sc-err-hint" id="sc-add-char-err"></div>
                        </div>
                        <div class="sc-clist" id="sc-clist"></div>
                    </aside>
                    <div class="sc-twrap">
                        <div class="sc-empty" id="sc-empty">暂无字幕内容</div>
                        <div class="sc-tscroll" id="sc-tscroll" style="display:none">
                            <table>
                                <thead>
                                <tr>
                                    <th class="sc-col-ck"><div class="sc-ck" id="sc-hdr-ck"></div></th>
                                    <th class="sc-col-idx">#</th>
                                    <th class="sc-col-time">时间码</th>
                                    <th class="sc-col-char">角色</th>
                                    <th class="sc-col-txt">字幕文本</th>
                                </tr>
                                </thead>
                                <tbody id="sc-tbody"></tbody>
                            </table>
                        </div>
                    </div>
                </div>
                <div class="sc-sbar">
                    <div class="sc-si"><span class="sc-sl">字幕</span><span id="sc-st-total">0</span></div>
                    <div class="sc-si"><span class="sc-sl">角色</span><span id="sc-st-chars">0</span></div>
                    <div class="sc-si"><span class="sc-sl">选中</span><span id="sc-st-sel">0</span></div>
                </div>
                <div class="sc-modal-bg" id="sc-modal-bg"><div class="sc-modal" id="sc-modal"></div></div>
                <div class="sc-toast-box" id="sc-toast"></div>
            </div>
        `;
        document.body.appendChild(this.overlay);

        this.fileInput = document.createElement("input");
        this.fileInput.type = "file";
        this.fileInput.accept = ".srt";
        this.fileInput.style.display = "none";
        this.overlay.appendChild(this.fileInput);

        this._bindDom();
    }

    $(s) { return this.overlay.querySelector(s); }
    $$(s) { return this.overlay.querySelectorAll(s); }

    _bindDom() {
        this.$("#sc-btn-close").onclick = () => this.close();
        this.$("#sc-btn-save").onclick = () => this.saveToNode();
        this.$("#sc-btn-reset").onclick = () => this.resetToOpenSnapshot();
        this.$("#sc-tb-open").onclick = () => this.fileInput.click();
        this.$("#sc-tb-save-file").onclick = () => this.downloadSrt();
        this.$("#sc-tb-export").onclick = () => this.showExportModal();
        this.$("#sc-hdr-ck").onclick = () => this.toggleAllSelection();

        this.$("#sc-add-char").onkeydown = (e) => {
            if (e.key === "Enter") this.addCharFromInput();
        };

        this.fileInput.onchange = async (e) => {
            const file = e.target.files?.[0];
            if (file) await this.loadFile(file);
            e.target.value = "";
        };

        this.overlay.addEventListener("keydown", (e) => {
            if (e.key === "Escape") this.close();
        });

        this.$("#sc-tbody").addEventListener("click", (e) => {
            const row = e.target.closest("tr[data-i]");
            if (!row) return;
            if (e.target.classList.contains("sc-edit-btn")) {
                this.startEdit(parseInt(row.dataset.i, 10));
                return;
            }
            if (e.target.closest(".sc-csel") || e.target.closest(".sc-tedit")) return;
            this.toggleSelection(parseInt(row.dataset.i, 10), e.shiftKey);
        });

        this.$("#sc-tbody").addEventListener("dblclick", (e) => {
            const cell = e.target.closest(".sc-tdisp");
            if (!cell) return;
            const row = e.target.closest("tr[data-i]");
            if (!row) return;
            e.stopPropagation();
            this.startEdit(parseInt(row.dataset.i, 10));
        });

        this.$("#sc-tbody").addEventListener("change", (e) => {
            if (e.target.classList.contains("sc-csel")) {
                const i = parseInt(e.target.dataset.sel, 10);
                this.subs[i].character = e.target.value;
                this.chars = ensureChar(this.chars, e.target.value);
                this.syncCurrentCache();
                this.render();
            }
        });

        this.$("#sc-clist").addEventListener("click", (e) => {
            const btn = e.target.closest(".sc-cdel");
            if (btn) {
                e.stopPropagation();
                this.removeChar(btn.dataset.name);
                return;
            }
            const item = e.target.closest(".sc-citem");
            if (item?.dataset?.char) this.selectByCharacter(item.dataset.char);
        });

        this.$("#sc-clist").addEventListener("dblclick", (e) => {
            const item = e.target.closest(".sc-citem");
            if (item?.dataset?.char) {
                e.stopPropagation();
                this.startRenameCharacter(item.dataset.char);
            }
        });
    }

    open(node, textWidget) {
        this.node = node;
        this.textWidget = textWidget;
        const state = getNodeState(node);
        const cache = state.subtitles?.length ? cloneState(state) : {
            sourceText: textWidget?.value || "",
            fileName: state.fileName || "",
            subtitles: parseSrt(textWidget?.value || ""),
            chars: [],
        };
        cache.subtitles.forEach((s) => { cache.chars = ensureChar(cache.chars, s.character); });
        this.subs = cache.subtitles;
        this.chars = cache.chars;
        this.fileName = cache.fileName;
        this.selectedSet.clear();
        this.editing = -1;
        this.lastClick = -1;
        setNodeState(node, {
            sourceText: cache.sourceText || buildSrt(cache.subtitles),
            fileName: cache.fileName,
            subtitles: cache.subtitles,
            chars: cache.chars,
            openSnapshot: cloneState({
                sourceText: cache.sourceText || buildSrt(cache.subtitles),
                fileName: cache.fileName,
                subtitles: cache.subtitles,
                chars: cache.chars,
            }),
        });
        this.overlay.style.display = "";
        this.overlay.focus();
        this.render();
    }

    close() { this.overlay.style.display = "none"; }

    syncCurrentCache() {
        if (!this.node) return;
        setNodeState(this.node, {
            sourceText: buildSrt(this.subs),
            fileName: this.fileName,
            subtitles: this.subs.map((s) => ({ ...s })),
            chars: this.chars.map((c) => ({ ...c })),
        });
    }

    resetToOpenSnapshot() {
        if (!this.node) return;
        const snapshot = getNodeState(this.node).openSnapshot;
        if (!snapshot) return;
        this.subs = snapshot.subtitles.map((s) => ({ ...s }));
        this.chars = snapshot.chars.map((c) => ({ ...c }));
        this.fileName = snapshot.fileName || "";
        this.selectedSet.clear();
        this.syncCurrentCache();
        if (this.textWidget) this.textWidget.value = snapshot.sourceText || buildSrt(this.subs);
        this.render();
        this.toast("已恢复到打开时状态", "ok");
    }

    saveToNode() {
        if (!this.node || !this.textWidget) return;
        const srt = buildSrt(this.subs);
        this.textWidget.value = srt;
        this.textWidget.callback?.(srt);
        const widgetIndex = this.node.widgets?.findIndex((w) => w.name === "srt_text") ?? -1;
        if (widgetIndex >= 0) {
            this.node.widgets[widgetIndex].value = srt;
            if (Array.isArray(this.node.widgets_values)) this.node.widgets_values[widgetIndex] = srt;
        }
        this.syncCurrentCache();
        this.node.setDirtyCanvas?.(true, true);
        this.node.graph?.change?.();
        app.graph?.setDirtyCanvas?.(true, true);
        this.toast("已保存到节点", "ok");
    }

    async loadFile(file) {
        if (!file.name.toLowerCase().endsWith(".srt")) {
            this.toast("请选择 .srt 文件", "err");
            return;
        }
        const text = await file.text();
        this.subs = parseSrt(text);
        this.fileName = file.name;
        this.chars = [];
        this.subs.forEach((s) => { this.chars = ensureChar(this.chars, s.character); });
        this.selectedSet.clear();
        this.syncCurrentCache();
        setNodeState(this.node, {
            openSnapshot: cloneState({
                sourceText: text,
                fileName: file.name,
                subtitles: this.subs,
                chars: this.chars,
            }),
        });
        this.render();
    }

    addCharFromInput() {
        const input = this.$("#sc-add-char");
        const err = this.$("#sc-add-char-err");
        const name = input.value.trim();
        if (!name) { err.textContent = "角色名不能为空"; return; }
        if (INVALID_FILE_CHARS.test(name)) { err.textContent = "角色名包含非法字符"; return; }
        if (this.chars.some((c) => c.name === name)) { err.textContent = "角色已存在"; return; }
        err.textContent = "";
        input.value = "";
        this.chars = ensureChar(this.chars, name);
        this.syncCurrentCache();
        this.render();
    }

    removeChar(name) {
        if (!name) return;
        this.chars = this.chars.filter((c) => c.name !== name);
        this.subs = this.subs.map((sub) => (sub.character === name ? { ...sub, character: "" } : sub));
        this.syncCurrentCache();
        this.render();
        this.toast(`已删除角色：${name}，相关字幕已改为未指定`, "ok");
    }

    startRenameCharacter(oldName) {
        this.$("#sc-modal").innerHTML = `
            <div class="sc-modal-t">批量重命名角色</div>
            <div class="sc-exp-row">
                <label>将角色 "<strong>${esc(oldName)}</strong>" 重命名为：</label>
                <input class="sc-cadd-input" id="sc-rename-input" value="${escAttr(oldName)}" style="margin-top:8px">
                <div class="sc-err-hint" id="sc-rename-err"></div>
            </div>
            <div class="sc-modal-acts">
                <button class="sc-mbtn sc-mbtn-cancel" id="sc-rename-cancel">取消</button>
                <button class="sc-mbtn sc-mbtn-ok" id="sc-rename-ok">确认重命名</button>
            </div>
        `;
        this.$("#sc-modal-bg").classList.add("on");
        
        const input = this.$("#sc-rename-input");
        input.focus();
        input.select();

        this.$("#sc-rename-cancel").onclick = () => this.hideModal();
        this.$("#sc-rename-ok").onclick = () => {
            const newName = input.value.trim();
            this.renameCharacter(oldName, newName);
        };
        
        input.onkeydown = (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                const newName = input.value.trim();
                this.renameCharacter(oldName, newName);
            }
        };
    }

    renameCharacter(oldName, newName) {
        const err = this.$("#sc-rename-err");
        
        if (!newName) {
            err.textContent = "角色名不能为空";
            return;
        }
        if (INVALID_FILE_CHARS.test(newName)) {
            err.textContent = "角色名包含非法字符";
            return;
        }
        if (newName === oldName) {
            this.hideModal();
            return;
        }

        if (this.chars.some(c => c.name === newName)) {
            err.textContent = "该角色名已存在，请使用其他名称！";
            return;
        }

        this.subs.forEach(s => {
            if (s.character === oldName) {
                s.character = newName;
            }
        });

        const charItem = this.chars.find(c => c.name === oldName);
        if (charItem) charItem.name = newName;

        this.hideModal();
        this.syncCurrentCache();
        this.render();
        this.toast(`已将角色 "${oldName}" 重命名为 "${newName}"`, "ok");
    }

    toggleSelection(index, shiftKey) {
        if (shiftKey && this.lastClick >= 0) {
            const from = Math.min(this.lastClick, index);
            const to = Math.max(this.lastClick, index);
            const shouldSelect = !this.selectedSet.has(index);
            for (let i = from; i <= to; i += 1) shouldSelect ? this.selectedSet.add(i) : this.selectedSet.delete(i);
        } else if (this.selectedSet.has(index)) {
            this.selectedSet.delete(index);
        } else {
            this.selectedSet.add(index);
        }
        this.lastClick = index;
        this.renderSelection();
    }

    toggleAllSelection() {
        if (this.selectedSet.size === this.subs.length) this.selectedSet.clear();
        else this.subs.forEach((_, i) => this.selectedSet.add(i));
        this.renderSelection();
    }

    selectByCharacter(name) {
        const indices = this.subs.map((s, i) => (s.character === name ? i : -1)).filter((i) => i >= 0);
        const allSelected = indices.length > 0 && indices.every((i) => this.selectedSet.has(i));
        indices.forEach((i) => { allSelected ? this.selectedSet.delete(i) : this.selectedSet.add(i); });
        this.renderSelection();
    }

    startEdit(index) {
        if (this.editing >= 0 && this.editing !== index) this.finishEdit(this.editing);
        this.editing = index;
        const display = this.$(`#sc-tdisp-${index}`);
        const textarea = this.$(`#sc-tedit-${index}`);
        const button = this.$(`#sc-ebtn-${index}`);
        if (!display || !textarea) return;
        display.style.display = "none";
        if (button) button.style.display = "none";
        textarea.value = this.subs[index].text;
        textarea.rows = Math.max(2, textarea.value.split("\n").length + 1);
        textarea.style.display = "block";
        textarea.onblur = () => this.finishEdit(index);
        textarea.onkeydown = (e) => {
            if (e.key === "Escape") { textarea.value = this.subs[index].text; textarea.blur(); }
            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); textarea.blur(); }
        };
        textarea.focus();
    }

    finishEdit(index) {
        if (this.editing !== index) return;
        this.editing = -1;
        const display = this.$(`#sc-tdisp-${index}`);
        const textarea = this.$(`#sc-tedit-${index}`);
        const button = this.$(`#sc-ebtn-${index}`);
        if (textarea) { this.subs[index].text = textarea.value; textarea.style.display = "none"; }
        if (display) display.style.display = "block";
        if (button) button.style.display = "";
        this.syncCurrentCache();
        this.render();
    }

    buildExportBody(sub, contentType) {
        if (contentType === "text") return sub.text;
        if (contentType === "char_text") return `${sub.character ? `[${sub.character}] ` : ""}${sub.text}`;
        if (contentType === "char_time_text") {
            const prefix = sub.character ? `[${sub.character}] ` : "";
            return `${sub.startRaw} --> ${sub.endRaw}\n${prefix}${sub.text}`;
        }
        return `${sub.index}\n${sub.startRaw} --> ${sub.endRaw}\n${sub.character ? `[${sub.character}] ` : ""}${sub.text}\n`;
    }

    buildExportBaseName(sub, nameType) {
        const safeChar = (sub.character || "未指定").replace(INVALID_FILE_CHARS, "_");
        const safeStart = sub.startRaw.replace(/[:,]/g, "-");
        if (nameType === "idx") return String(sub.index).padStart(3, "0");
        if (nameType === "char_idx") return `${safeChar}_${String(sub.index).padStart(3, "0")}`;
        if (nameType === "idx_start") return `${String(sub.index).padStart(3, "0")}_${safeStart}`;
        if (nameType === "start") return safeStart;
        return `${String(sub.index).padStart(3, "0")}_${safeChar}`;
    }

    showExportModal() {
        const selectedCount = this.selectedSet.size;
        const totalCount = this.subs.length;
        this.$("#sc-modal").innerHTML = `
            <div class="sc-modal-t">批量导出</div>
            <div class="sc-exp-row"><label>文件名格式</label>
                <select id="sc-exp-name">
                    <option value="idx_char">序号_角色名</option>
                    <option value="idx">仅序号</option>
                    <option value="char_idx">角色名_序号</option>
                    <option value="idx_start">序号_开始时间</option>
                    <option value="start">仅开始时间</option>
                </select>
            </div>
            <div class="sc-exp-row"><label>文件内容</label>
                <select id="sc-exp-content">
                    <option value="text">仅字幕文本</option>
                    <option value="char_text">角色 + 字幕文本</option>
                    <option value="char_time_text">角色 + 时间码 + 字幕文本</option>
                    <option value="srt">标准 SRT 格式</option>
                </select>
            </div>
            <div class="sc-exp-row"><label>文件扩展名</label>
                <select id="sc-exp-ext">
                    <option value=".txt">.txt</option>
                    <option value=".srt">.srt</option>
                </select>
            </div>
            <div class="sc-exp-row"><label>导出范围</label>
                <select id="sc-exp-range">
                    <option value="selected">仅选中（${selectedCount} 条）</option>
                    <option value="all" selected>全部（${totalCount} 条）</option>
                </select>
            </div>
            <div class="sc-modal-acts">
                <button class="sc-mbtn sc-mbtn-cancel" id="sc-exp-cancel">取消</button>
                <button class="sc-mbtn sc-mbtn-ok" id="sc-exp-do">导出 ZIP</button>
            </div>
        `;
        this.$("#sc-modal-bg").classList.add("on");
        this.$("#sc-exp-cancel").onclick = () => this.hideModal();
        this.$("#sc-exp-do").onclick = () => this.exportZip();
    }

    hideModal() { this.$("#sc-modal-bg").classList.remove("on"); }

    async exportZip() {
        const range = this.$("#sc-exp-range").value;
        const nameType = this.$("#sc-exp-name").value;
        const contentType = this.$("#sc-exp-content").value;
        const extension = this.$("#sc-exp-ext").value;
        const items = range === "selected" ? this.subs.filter((_, i) => this.selectedSet.has(i)) : [...this.subs];
        if (!items.length) { this.toast("没有可导出的内容", "err"); return; }

        if (typeof JSZip === "undefined") {
            await new Promise((resolve, reject) => {
                const script = document.createElement("script");
                script.src = "https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js";
                script.onload = resolve;
                script.onerror = reject;
                document.head.appendChild(script);
            });
        }

        const zip = new JSZip();
        const fileNameCounter = {};
        items.forEach((sub) => {
            const roleFolder = (sub.character || "未指定").replace(INVALID_FILE_CHARS, "_");
            let baseName = this.buildExportBaseName(sub, nameType);
            let exportPath = `${roleFolder}/${baseName}${extension}`;
            fileNameCounter[exportPath] = (fileNameCounter[exportPath] || 0) + 1;
            if (fileNameCounter[exportPath] > 1) {
                baseName = `${baseName}_${fileNameCounter[exportPath]}`;
                exportPath = `${roleFolder}/${baseName}${extension}`;
            }
            zip.file(exportPath, this.buildExportBody(sub, contentType));
        });

        const blob = await zip.generateAsync({ type: "blob" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${(this.fileName || "subtitle").replace(/\.srt$/i, "")}_导出.zip`;
        a.click();
        URL.revokeObjectURL(url);
        this.hideModal();
        this.toast("已导出 ZIP", "ok");
    }

    downloadSrt() {
        if (!this.subs.length) return;
        const blob = new Blob([buildSrt(this.subs)], { type: "text/plain;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = this.fileName || "subtitle.srt";
        a.click();
        URL.revokeObjectURL(url);
    }

    renderSelection() {
        this.$$("#sc-tbody tr").forEach((row, i) => {
            const selected = this.selectedSet.has(i);
            row.classList.toggle("sel", selected);
            const ck = row.querySelector(".sc-ck");
            if (ck) ck.className = selected ? "sc-ck on" : "sc-ck";
        });
        const total = this.subs.length;
        const selected = this.selectedSet.size;
        this.$("#sc-hdr-ck").className = selected === 0 ? "sc-ck" : selected === total ? "sc-ck on" : "sc-ck part";
        this.$("#sc-st-sel").textContent = String(selected);
    }

    render() {
        this.$("#sc-filename").textContent = this.fileName;
        this.$("#sc-st-total").textContent = String(this.subs.length);
        this.$("#sc-st-chars").textContent = String(this.chars.length);
        this.$("#sc-st-sel").textContent = String(this.selectedSet.size);
        this.$("#sc-empty").style.display = this.subs.length ? "none" : "flex";
        this.$("#sc-tscroll").style.display = this.subs.length ? "block" : "none";

        if (!this.subs.length) {
            this.$("#sc-clist").innerHTML = "";
            this.$("#sc-tbody").innerHTML = "";
            return;
        }

        this.$("#sc-clist").innerHTML = this.chars.map((c) => `
            <div class="sc-citem" data-char="${escAttr(c.name)}">
                <div class="sc-cdot" style="background:${c.color}"></div>
                <span class="sc-cname">${esc(c.name)}</span>
                <span class="sc-ccount">${this.subs.filter((s) => s.character === c.name).length}</span>
                <button class="sc-cdel" data-name="${escAttr(c.name)}">×</button>
            </div>
        `).join("");

        this.$("#sc-tbody").innerHTML = this.subs.map((s, i) => {
            const color = s.character ? this.chars.find((c) => c.name === s.character)?.color || "#4a506a" : "#4a506a";
            const options = this.chars.map((c) => `<option value="${escAttr(c.name)}" style="color:${c.color};"${c.name === s.character ? " selected" : ""}>${esc(c.name)}</option>`).join("");
            
            return `
            <tr data-i="${i}">
                <td class="sc-col-ck"><div class="${this.selectedSet.has(i) ? "sc-ck on" : "sc-ck"}"></div></td>
                <td class="sc-col-idx">${s.index}</td>
                <td class="sc-col-time">
                    <div class="sc-timecell">
                        <div class="sc-time-start">${esc(s.start)} <span class="sc-time-arrow">→</span></div>
                        <div class="sc-time-end">${esc(s.end)}</div>
                    </div>
                </td>
                <td class="sc-col-char">
                    <select class="sc-csel" data-sel="${i}" style="color:${s.character ? color : '#7b829a'};">
                        <option value="" style="color:#7b829a;">未指定</option>
                        ${options}
                    </select>
                </td>
                <td class="sc-col-txt sc-txt-cell">
                    <div class="sc-tdisp" id="sc-tdisp-${i}">${esc(s.text)}</div>
                    <textarea class="sc-tedit" id="sc-tedit-${i}" style="display:none"></textarea>
                    <button class="sc-edit-btn" id="sc-ebtn-${i}"><i class="fa-solid fa-pen"></i></button>
                </td>
            </tr>
            `;
        }).join("");

        this.renderSelection();
    }

    toast(msg, type = "inf") {
        const box = this.$("#sc-toast");
        const el = document.createElement("div");
        el.className = `sc-toast ${type}`;
        el.textContent = msg;
        box.appendChild(el);
        setTimeout(() => { el.classList.add("out"); setTimeout(() => el.remove(), 300); }, 2000);
    }
}

const dialog = new SubCastDialog();

function installSubCastNodeUi(nodeType) {
    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
        const result = onNodeCreated?.apply(this, arguments);
        const textWidget = this.widgets?.find((w) => w.name === "srt_text");
        if (!textWidget) return result;

        const openEditor = () => dialog.open(this, textWidget);

        const hasDomBtn = this.widgets?.some((w) => w.name === "easyuse_subcast_btn");
        if (!hasDomBtn && this.addDOMWidget) {
            const container = document.createElement("div");
            container.style.cssText = "width:100%;margin:4px 0 6px 0;";
            container.innerHTML = `
                <button style="
                    width:100%;
                    padding:10px 0;
                    background:linear-gradient(135deg, #f59e0b, #f97316);
                    color:#000;
                    border:none;
                    border-radius:8px;
                    font-size:13px;
                    font-weight:600;
                    cursor:pointer;
                    box-sizing:border-box;
                    display:block;
                ">打开 SubCast 编辑器</button>
            `;
            container.querySelector("button")?.addEventListener("click", openEditor);
            this.addDOMWidget("easyuse_subcast_btn", "custom", container, { getValue: () => "", setValue: () => {} });
        }

        textWidget.hidden = true;
        textWidget.computeSize = () => [0, -6];

        if (!this.__easyuseSubcastPreviewEl && this.addDOMWidget) {
            const preview = document.createElement("div");
            preview.style.cssText = [
                "width:100%",
                "min-height:56px",
                "max-height:88px",
                "padding:10px 12px",
                "margin-top:4px",
                "border-radius:8px",
                "background:#171922",
                "border:1px solid #2a3040",
                "color:#bfc7d8",
                "font-size:12px",
                "line-height:1.5",
                "white-space:pre-wrap",
                "overflow:hidden",
            ].join(";");
            preview.textContent = "暂无字幕内容";
            this.__easyuseSubcastPreviewEl = preview;
            this.addDOMWidget("easyuse_subcast_preview", "custom", preview, { getValue: () => "", setValue: () => {} });
        }

        updatePreview(this);
        this.size = [Math.max(this.size?.[0] || 0, 420), Math.max(this.size?.[1] || 0, 280)];
        return result;
    };

    const onSerialize = nodeType.prototype.onSerialize;
    nodeType.prototype.onSerialize = function (o) {
        onSerialize?.apply(this, arguments);
        if (this.__easyuseSubcastState) o.easyuse_subcast_data = this.__easyuseSubcastState;
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function (o) {
        onConfigure?.apply(this, arguments);
        if (!o.easyuse_subcast_data) return;
        this.__easyuseSubcastState = {
            ...o.easyuse_subcast_data,
            subtitles: (o.easyuse_subcast_data.subtitles || []).map((s) => ({ ...s })),
            chars: (o.easyuse_subcast_data.chars || []).map((c) => ({ ...c })),
            openSnapshot: o.easyuse_subcast_data.openSnapshot ? cloneState(o.easyuse_subcast_data.openSnapshot) : null,
        };
        const textWidget = this.widgets?.find((w) => w.name === "srt_text");
        if (textWidget && this.__easyuseSubcastState.sourceText) textWidget.value = this.__easyuseSubcastState.sourceText;
        updatePreview(this);
    };
}

app.registerExtension({
    name: "Comfy.EasyUse.SubCast",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        const names = [nodeData?.name, nodeData?.display_name, nodeType?.type, nodeType?.title].filter(Boolean).join(" | ");
        if (!/Easy Use SubCast Editor|EasyUseSubCastEditor/i.test(names)) return;
        installSubCastNodeUi(nodeType);
    },
});
