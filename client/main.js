const path = require('path')
const url = require('url')
const { app, BrowserWindow, ipcMain, dialog, Menu } = require('electron')

// require('electron-reload')(__dirname, {
//   electron: require(path.join(__dirname, 'node_modules', 'electron'))
// })

let mainWindow

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      webSecurity: false,
      allowRunningInsecureContent: true
    }
  })

  // Standard React App Logic
  let startUrl
  if (process.env.ENVIRONMENT === 'development') {
    startUrl = 'http://localhost:3000'
  } else {
    startUrl = url.format({
      pathname: path.join(__dirname, 'build', 'index.html'),
      protocol: 'file:',
      slashes: true
    })
  }

  mainWindow.loadURL(startUrl)

  // comment out to stop dev tools from opening
  // mainWindow.webContents.openDevTools();

  mainWindow.on('closed', () => {
    mainWindow = null
  })

  createMenu()
}

function createMenu() {
  const isMac = process.platform === 'darwin'

  const template = [
    {
      label: 'File',
      submenu: [
        {
          label: 'Change Startup Mode...',
          click: () => {
            // Send IPC to Renderer to clear user asset
            if (mainWindow) {
              mainWindow.webContents.send('reset-preference')
            }
          }
        },
        { role: 'quit' }
      ]
    },
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' }
      ]
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        // Custom Tab Toggles
        {
          label: 'File Management',
          type: 'checkbox',
          checked: true,
          enabled: false, // Always on
        },
        {
          label: 'Visualization',
          type: 'checkbox',
          checked: false,
          click: (menuItem) => mainWindow.webContents.send('toggle-tab', 'visualization', menuItem.checked)
        },
        {
          label: 'Model Training',
          type: 'checkbox',
          checked: false,
          click: (menuItem) => mainWindow.webContents.send('toggle-tab', 'training', menuItem.checked)
        },
        {
          label: 'Model Inference',
          type: 'checkbox',
          checked: false,
          click: (menuItem) => mainWindow.webContents.send('toggle-tab', 'inference', menuItem.checked)
        },
        {
          label: 'Tensorboard',
          type: 'checkbox',
          checked: false,
          click: (menuItem) => mainWindow.webContents.send('toggle-tab', 'monitoring', menuItem.checked)
        },
        {
          label: 'SynAnno',
          type: 'checkbox',
          checked: false,
          click: (menuItem) => mainWindow.webContents.send('toggle-tab', 'synanno', menuItem.checked)
        },
        {
          label: 'Worm Error Handling',
          type: 'checkbox',
          checked: false,
          click: (menuItem) => mainWindow.webContents.send('toggle-tab', 'worm-error-handling', menuItem.checked)
        }
      ]
    },
    {
      label: 'Help',
      submenu: [
        {
          label: 'About',
          click: async () => {
            const { shell } = require('electron')
            await shell.openExternal('https://github.com/google-deepmind')
          }
        }
      ]
    }
  ]

  const menu = Menu.buildFromTemplate(template)
  Menu.setApplicationMenu(menu)
}

ipcMain.handle('dialog:openFile', async (event, options = {}) => {
  const properties = options.properties || ['openFile', 'openDirectory']
  const { canceled, filePaths } = await dialog.showOpenDialog(mainWindow, {
    properties
  })
  if (canceled) {
    return null
  } else {
    return filePaths[0]
  }
})

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
