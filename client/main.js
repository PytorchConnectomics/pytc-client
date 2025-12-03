const path = require('path')
const url = require('url')
const { app, BrowserWindow } = require('electron')
require('electron-reload')(__dirname, {
  electron: require(path.join(__dirname, 'node_modules', 'electron'))
})

let mainWindow

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    }
  })

  if (process.env.ENVIRONMENT === 'development') {
    mainWindow.loadURL('http://localhost:3000')
  } else {
    mainWindow.loadURL(url.format({
      pathname: path.join(__dirname, 'build', 'index.html'),
      protocol: 'file:',
      slashes: true
    }))
  }

  // comment out to stop dev tools from opening
  // mainWindow.webContents.openDevTools();

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

app.on('ready', createWindow)

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow()
  }
})
