const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

let mainWindow = null;
let pythonProcess = null;

const API_PORT = 8765;
const API_URL = `http://127.0.0.1:${API_PORT}`;

// Check if Python API server is already running
function checkServerRunning() {
  return new Promise((resolve) => {
    http.get(`${API_URL}/api/status`, (res) => {
      resolve(res.statusCode === 200);
    }).on('error', () => {
      resolve(false);
    });
  });
}

// Start Python FastAPI backend if needed
async function ensureBackendStarted() {
  const isRunning = await checkServerRunning();
  if (isRunning) {
    console.log('[Electron] Python API bridge already running at', API_URL);
    return;
  }

  const projectRoot = path.resolve(__dirname, '../..');
  const pythonExecutable = path.join(projectRoot, '.venv/Scripts/python.exe');

  console.log('[Electron] Starting Python API server from:', pythonExecutable);

  pythonProcess = spawn(
    pythonExecutable,
    ['-m', 'intellifile.api.server'],
    {
      cwd: projectRoot,
      env: { ...process.env, PYTHONPATH: path.join(projectRoot, 'src') },
      stdio: 'inherit',
    }
  );

  pythonProcess.on('error', (err) => {
    console.error('[Electron] Failed to start Python process:', err);
  });

  // Wait for server to become responsive
  for (let i = 0; i < 30; i++) {
    await new Promise((r) => setTimeout(r, 500));
    if (await checkServerRunning()) {
      console.log('[Electron] Python API bridge is ready!');
      return;
    }
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1360,
    height: 880,
    minWidth: 1080,
    minHeight: 700,
    backgroundColor: '#0a0b0e',
    title: 'FILE XTRACTOR',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
    },
  });

  // In production or when server is mounted, load API_URL
  mainWindow.loadURL(API_URL);

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// IPC Handlers
ipcMain.handle('select-folder', async () => {
  if (!mainWindow) return null;
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
  });
  if (result.canceled || result.filePaths.length === 0) return null;
  return result.filePaths[0];
});

app.whenReady().then(async () => {
  await ensureBackendStarted();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('will-quit', () => {
  if (pythonProcess) {
    pythonProcess.kill();
  }
});
