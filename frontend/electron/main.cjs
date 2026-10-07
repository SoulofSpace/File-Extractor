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
    title: 'i-file',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
    },
  });

  // Clear HTTP/session cache on startup to ensure latest build loads immediately
  mainWindow.webContents.session.clearCache();

  // In production or when server is mounted, load API_URL
  mainWindow.loadURL(API_URL);

  // Forward console messages to terminal for instant debugging
  mainWindow.webContents.on('console-message', (event, level, message, line, sourceId) => {
    const levels = ['DEBUG', 'INFO', 'WARN', 'ERROR'];
    console.log(`[Renderer ${levels[level] || level}] ${message} (${sourceId}:${line})`);
  });

  // Enable F5 / Ctrl+R reload, and F12 / Ctrl+Shift+I DevTools
  mainWindow.webContents.on('before-input-event', (event, input) => {
    if (input.key === 'F5' || (input.control && input.key.toLowerCase() === 'r')) {
      mainWindow.reload();
      event.preventDefault();
    }
    if (input.key === 'F12' || (input.control && input.shift && input.key.toLowerCase() === 'i')) {
      mainWindow.webContents.toggleDevTools();
      event.preventDefault();
    }
  });

  // Auto-retry if backend server was binding
  mainWindow.webContents.on('did-fail-load', () => {
    console.log('[Electron] Initial page load failed, retrying in 1.5s...');
    setTimeout(() => {
      if (mainWindow) mainWindow.loadURL(API_URL);
    }, 1500);
  });

  // Automated visual verification snapshot
  mainWindow.webContents.on('did-finish-load', () => {
    if (process.argv.includes('--screenshot')) {
      setTimeout(async () => {
        try {
          const image = await mainWindow.webContents.capturePage();
          const fs = require('fs');
          const outPath = path.resolve(__dirname, '../../electron_screenshot.png');
          fs.writeFileSync(outPath, image.toPNG());
          console.log('[Electron] Screenshot successfully saved to:', outPath);
        } catch (e) {
          console.error('[Electron] Screenshot failed:', e);
        }
      }, 3500);
    }

    if (process.argv.includes('--test-preview')) {
      setTimeout(async () => {
        try {
          await mainWindow.webContents.executeJavaScript(`
            (() => {
              const card = document.querySelector('.file-card');
              if (card) {
                card.click();
                console.log('[Electron Test] Card clicked successfully');
              } else {
                console.warn('[Electron Test] No .file-card found');
              }
            })()
          `);

          // Wait 1 second for slide-in drawer
          setTimeout(async () => {
            const image = await mainWindow.webContents.capturePage();
            const fs = require('fs');
            const outPath = path.resolve(__dirname, '../../electron_preview_screenshot.png');
            fs.writeFileSync(outPath, image.toPNG());
            console.log('[Electron] Preview screenshot saved to:', outPath);
          }, 1000);
        } catch (e) {
          console.error('[Electron] Test preview failed:', e);
        }
      }, 3500);
    }
  });

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
