const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("ryanDam", {
  getBackendInfo: () => ipcRenderer.invoke("backend:get-info"),
  createSampleFile: () => ipcRenderer.invoke("drag:create-sample"),
  startSampleDrag: () => ipcRenderer.send("drag:start-sample")
});
