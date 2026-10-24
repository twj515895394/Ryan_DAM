const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("ryanDam", {
  getBackendInfo: () => ipcRenderer.invoke("backend:get-info"),
  selectFiles: () => ipcRenderer.invoke("dialog:select-files"),
  selectFolder: () => ipcRenderer.invoke("dialog:select-folder"),
  createSampleFile: () => ipcRenderer.invoke("drag:create-sample"),
  startSampleDrag: () => ipcRenderer.send("drag:start-sample")
});
