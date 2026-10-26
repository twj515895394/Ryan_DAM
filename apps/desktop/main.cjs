const { app, BrowserWindow, dialog, ipcMain, Menu, nativeImage, screen } = require("electron");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const { spawn } = require("node:child_process");

app.setName("Ryan_DAM");
// Must match electron-builder build.appId so Windows attributes the taskbar button
// to our shortcut (RD icon) instead of the default Electron host icon.
app.setAppUserModelId("com.ryandam.desktop");
// RYAN_DAM_USER_DATA lets dev/test runs isolate all local data (DB, logs, window state).
const localDataRoot = process.env.RYAN_DAM_USER_DATA || process.env.LOCALAPPDATA || app.getPath("appData");
app.setPath("userData", path.join(localDataRoot, "Ryan_DAM"));

const userDataPath = app.getPath("userData");
const logDirectory = path.join(userDataPath, "logs");
const logFile = path.join(logDirectory, "desktop.log");
const windowStateFile = path.join(userDataPath, "window-state.json");
const sampleDirectory = path.join(userDataPath, "stage0-poc");
const samplePath = path.join(sampleDirectory, "sample-upload.txt");
const appIconPath = path.join(__dirname, "assets", "icon.png");
const dragIconPath = path.join(__dirname, "assets", "drag-icon.png");

let mainWindow = null;
let backendProcess = null;
let backendInfo = null;
let dragSamplePath = null;
let isQuitting = false;
let lastWindowBounds = { width: 1440, height: 900 };
let saveWindowTimer = null;

function log(level, message) {
  const line = `${new Date().toISOString()} [${level}] ${message}\n`;
  try {
    fs.mkdirSync(logDirectory, { recursive: true });
    fs.appendFileSync(logFile, line, "utf8");
  } catch (_) {}
  if (level === "ERROR") console.error(line.trimEnd());
  else console.log(line.trimEnd());
}

function readWindowState() {
  const fallback = { width: 1440, height: 900, isMaximized: false };
  try {
    const saved = JSON.parse(fs.readFileSync(windowStateFile, "utf8"));
    const width = Number.isFinite(saved.width) ? Math.max(960, saved.width) : fallback.width;
    const height = Number.isFinite(saved.height) ? Math.max(640, saved.height) : fallback.height;
    const x = Number.isFinite(saved.x) ? saved.x : undefined;
    const y = Number.isFinite(saved.y) ? saved.y : undefined;
    const display = screen.getDisplayMatching({ x: x ?? 0, y: y ?? 0, width, height });
    const area = display.workArea;
    const safeWidth = Math.min(width, area.width);
    const safeHeight = Math.min(height, area.height);
    return {
      x: Math.max(area.x, Math.min(x ?? area.x + Math.round((area.width - safeWidth) / 2), area.x + area.width - Math.min(320, safeWidth))),
      y: Math.max(area.y, Math.min(y ?? area.y + Math.round((area.height - safeHeight) / 2), area.y + area.height - Math.min(160, safeHeight))),
      width: safeWidth,
      height: safeHeight,
      isMaximized: Boolean(saved.isMaximized)
    };
  } catch (_) {
    const area = screen.getPrimaryDisplay().workArea;
    return {
      x: area.x + Math.max(0, Math.round((area.width - fallback.width) / 2)),
      y: area.y + Math.max(0, Math.round((area.height - fallback.height) / 2)),
      width: Math.min(fallback.width, area.width),
      height: Math.min(fallback.height, area.height),
      isMaximized: false
    };
  }
}

function persistWindowState() {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  if (!mainWindow.isMaximized() && !mainWindow.isMinimized()) lastWindowBounds = mainWindow.getBounds();
  const state = { ...lastWindowBounds, isMaximized: mainWindow.isMaximized() };
  try {
    fs.mkdirSync(userDataPath, { recursive: true });
    fs.writeFileSync(windowStateFile, JSON.stringify(state, null, 2), "utf8");
  } catch (error) {
    log("ERROR", `Could not persist window state: ${error.message}`);
  }
}

function scheduleWindowStateSave() {
  if (saveWindowTimer) clearTimeout(saveWindowTimer);
  saveWindowTimer = setTimeout(() => {
    saveWindowTimer = null;
    persistWindowState();
  }, 180);
}

function getBackendCommand() {
  if (app.isPackaged) {
    const executable = path.join(process.resourcesPath, "backend", "ryan-dam-api.exe");
    if (!fs.existsSync(executable)) {
      throw new Error(`Bundled Python backend was not found: ${executable}\nRun the Windows package command after installing backend requirements.`);
    }
    return { command: executable, args: [], cwd: userDataPath };
  }
  return {
    command: process.env.RYAN_DAM_PYTHON || (process.platform === "win32" ? "python" : "python3"),
    args: ["-m", "backend.app.main"],
    cwd: app.getAppPath()
  };
}

function startBackend() {
  const token = crypto.randomBytes(32).toString("hex");
  const dataDirectory = path.join(userDataPath, "data");
  fs.mkdirSync(dataDirectory, { recursive: true });
  const launch = getBackendCommand();
  log("INFO", `Starting backend command: ${path.basename(launch.command)}`);
  backendProcess = spawn(launch.command, launch.args, {
    cwd: launch.cwd,
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
    env: {
      ...process.env,
      RYAN_DAM_API_TOKEN: token,
      RYAN_DAM_DATA_DIR: dataDirectory,
      RYAN_DAM_CACHE_DIR: path.join(userDataPath, "cache", "thumbnails"),
      PYTHONUNBUFFERED: "1"
    }
  });

  const child = backendProcess;
  return new Promise((resolve, reject) => {
    let settled = false;
    let stdoutBuffer = "";
    const readyPrefix = "RYAN_DAM_READY ";
    const timeout = setTimeout(() => fail(new Error("Python backend did not become ready within 20 seconds. Check the local app logs.")), 20000);

    function fail(error) {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      log("ERROR", error.message);
      try { child.kill(); } catch (_) {}
      reject(error);
    }

    function handleLine(line) {
      if (!line) return;
      if (line.startsWith(readyPrefix)) {
        try {
          const ready = JSON.parse(line.slice(readyPrefix.length));
          backendInfo = { baseUrl: `http://127.0.0.1:${ready.port}`, token, version: ready.version || "0.1.0" };
          if (!settled) {
            settled = true;
            clearTimeout(timeout);
            log("INFO", `Backend ready on 127.0.0.1:${ready.port}`);
            resolve(backendInfo);
          }
        } catch (error) {
          fail(new Error(`Invalid backend readiness payload: ${error.message}`));
        }
        return;
      }
      log("INFO", `[backend stdout] ${line}`);
    }

    child.stdout.on("data", (chunk) => {
      stdoutBuffer += chunk.toString("utf8");
      const lines = stdoutBuffer.split(/\r?\n/);
      stdoutBuffer = lines.pop() || "";
      lines.forEach(handleLine);
    });
    child.stderr.on("data", (chunk) => log("INFO", `[backend stderr] ${chunk.toString("utf8").trimEnd()}`));
    child.on("error", (error) => fail(new Error(`Failed to start Python backend: ${error.message}`)));
    child.on("close", (code) => {
      if (!settled) {
        fail(new Error(`Python backend exited before becoming ready (code ${code}).`));
        return;
      }
      if (!isQuitting && mainWindow) {
        log("ERROR", `Python backend exited unexpectedly (code ${code}).`);
        dialog.showErrorBox("Ryan_DAM 本地服务已停止", "本地 Python 服务意外退出。请查看 %LOCALAPPDATA%\\\\Ryan_DAM\\\\logs\\\\desktop.log 后重新启动应用。");
        app.quit();
      }
    });
  });
}

async function stopBackend() {
  const child = backendProcess;
  backendProcess = null;
  if (!child || child.exitCode !== null || child.signalCode !== null) return;
  if (backendInfo) {
    try {
      await fetch(`${backendInfo.baseUrl}/shutdown`, { method: "POST", headers: { "X-Ryan-DAM-Token": backendInfo.token } });
    } catch (_) {}
  }
  await Promise.race([
    new Promise((resolve) => child.once("close", resolve)),
    new Promise((resolve) => setTimeout(resolve, 1500))
  ]);
  if (child.exitCode === null && child.signalCode === null) {
    try { child.kill(); } catch (_) {}
  }
  backendInfo = null;
}

function createWindow() {
  const state = readWindowState();
  lastWindowBounds = { x: state.x, y: state.y, width: state.width, height: state.height };
  mainWindow = new BrowserWindow({
    x: state.x, y: state.y, width: state.width, height: state.height,
    minWidth: 960, minHeight: 640, show: false, backgroundColor: "#F5F5F7", title: "Ryan_DAM",
    icon: appIconPath,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true, nodeIntegration: false, sandbox: true, webSecurity: true
    }
  });
  mainWindow.once("ready-to-show", () => {
    if (state.isMaximized) mainWindow.maximize();
    mainWindow.show();
  });
  mainWindow.on("resize", scheduleWindowStateSave);
  mainWindow.on("move", scheduleWindowStateSave);
  mainWindow.on("maximize", scheduleWindowStateSave);
  mainWindow.on("unmaximize", scheduleWindowStateSave);
  mainWindow.on("close", persistWindowState);
  mainWindow.on("closed", () => { mainWindow = null; });

  const devServerUrl = process.env.RYAN_DAM_DEV_SERVER_URL;
  if (!app.isPackaged && devServerUrl) {
    mainWindow.loadURL(devServerUrl);
    if (process.env.RYAN_DAM_OPEN_DEVTOOLS === "1") mainWindow.webContents.openDevTools({ mode: "detach" });
  } else {
    mainWindow.loadFile(path.join(__dirname, "..", "web", "dist", "index.html"));
  }
}

ipcMain.handle("backend:get-info", () => {
  if (!backendInfo) throw new Error("本地服务尚未启动完成");
  return backendInfo;
});

ipcMain.handle("dialog:select-files", async (event) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  const options = {
    title: "选择要导入的文件",
    properties: ["openFile", "multiSelections", "dontAddToRecent"]
  };
  const result = win ? await dialog.showOpenDialog(win, options) : await dialog.showOpenDialog(options);
  if (result.canceled) return [];
  return result.filePaths;
});

ipcMain.handle("dialog:select-folder", async (event) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  const options = {
    title: "选择要导入的文件夹（将保留子目录层级）",
    properties: ["openDirectory", "dontAddToRecent"]
  };
  const result = win ? await dialog.showOpenDialog(win, options) : await dialog.showOpenDialog(options);
  if (result.canceled || result.filePaths.length === 0) return null;
  return result.filePaths[0];
});

ipcMain.handle("drag:create-sample", async () => {
  await fs.promises.mkdir(sampleDirectory, { recursive: true });
  const content = ["Ryan_DAM stage-0 native file drag test", "This is a generated test file. It is safe to delete.", `Created at: ${new Date().toISOString()}`].join("\r\n");
  await fs.promises.writeFile(samplePath, content, "utf8");
  dragSamplePath = samplePath;
  log("INFO", "Created the stage-0 drag sample.");
  return { name: path.basename(samplePath) };
});

ipcMain.on("drag:start-sample", (event) => {
  if (!dragSamplePath || !fs.existsSync(dragSamplePath)) {
    log("ERROR", "Drag requested before a sample file was created.");
    return;
  }
  const icon = nativeImage.createFromPath(dragIconPath);
  event.sender.startDrag({ file: dragSamplePath, icon });
});

// 票 21：受控正式资产拖出（按资产 ID 经本地后端鉴权校验真实路径，防任意路径逃逸）
const assetPathCache = new Map();

async function verifyAndCacheAsset(assetId) {
  if (!backendInfo || typeof assetId !== "number" || !Number.isInteger(assetId) || assetId <= 0) {
    return null;
  }
  try {
    const res = await fetch(`${backendInfo.baseUrl}/api/v1/assets/${assetId}`, {
      headers: { "X-Ryan-DAM-Token": backendInfo.token }
    });
    if (!res.ok) return null;
    const data = await res.json();
    if (data && typeof data.file_path === "string" && fs.existsSync(data.file_path)) {
      assetPathCache.set(assetId, { filePath: data.file_path, time: Date.now() });
      return data.file_path;
    }
  } catch (err) {
    log("WARN", `Failed to verify asset ${assetId}: ${err?.message || err}`);
  }
  return null;
}

ipcMain.handle("drag:prepare-asset", async (_event, assetId) => {
  return await verifyAndCacheAsset(assetId);
});

ipcMain.on("drag:start-asset", async (event, assetId) => {
  if (typeof assetId !== "number") return;
  const cached = assetPathCache.get(assetId);
  let filePath = cached ? cached.filePath : null;
  if (!filePath || !fs.existsSync(filePath)) {
    filePath = await verifyAndCacheAsset(assetId);
  }
  if (filePath && fs.existsSync(filePath)) {
    const icon = nativeImage.createFromPath(dragIconPath);
    event.sender.startDrag({ file: filePath, icon });
    log("INFO", `Started native drag for asset ${assetId}: ${filePath}`);
  } else {
    log("WARN", `Asset ${assetId} file unavailable on disk for native drag`);
  }
});

app.on("before-quit", (event) => {
  if (isQuitting) return;
  event.preventDefault();
  isQuitting = true;
  persistWindowState();
  stopBackend().finally(() => app.quit());
});
app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });
app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0 && backendInfo) createWindow();
});
function buildAppMenu() {
  const template = [
    {
      label: "文件",
      submenu: [{ role: "quit", label: "退出" }]
    },
    {
      label: "视图",
      submenu: [
        { role: "reload", label: "重新加载" },
        { role: "forceReload", label: "强制重新加载" },
        { role: "toggleDevTools", label: "开发者工具" },
        { type: "separator" },
        { role: "resetZoom", label: "实际大小" },
        { role: "zoomIn", label: "放大" },
        { role: "zoomOut", label: "缩小" }
      ]
    },
    {
      label: "帮助",
      submenu: [
        {
          label: "关于 Ryan_DAM",
          click: () => {
            dialog.showMessageBox({
              type: "info",
              title: "关于 Ryan_DAM",
              message: `Ryan_DAM ${app.getVersion()}`,
              detail: "本地优先的个人数字资产管理工具。"
            });
          }
        }
      ]
    }
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

app.whenReady().then(async () => {
  try {
    buildAppMenu();
    fs.mkdirSync(userDataPath, { recursive: true });
    await startBackend();
    createWindow();
  } catch (error) {
    log("ERROR", error instanceof Error ? error.stack || error.message : String(error));
    dialog.showErrorBox("Ryan_DAM 启动失败", `无法启动本地 Python 服务。请安装 backend/requirements.txt 中的依赖，或查看日志：${logFile}\n\n${error instanceof Error ? error.message : String(error)}`);
    app.quit();
  }
});
