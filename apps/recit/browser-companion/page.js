const start = document.querySelector('#start'), stop = document.querySelector('#stop');
const download = document.querySelector('#download');
let downloadUrl;
const recorder = new TabRecorder(chrome.desktopCapture, navigator.mediaDevices, MediaRecorder,
  message => {
    document.querySelector('#status').textContent = message;
    start.disabled = recorder.state !== 'idle'; stop.disabled = recorder.state === 'idle';
  }, blob => {
    if (downloadUrl) URL.revokeObjectURL(downloadUrl);
    downloadUrl = URL.createObjectURL(blob); download.href = downloadUrl;
    download.download = `recit-tab-${new Date().toISOString().replaceAll(':','-')}.webm`;
    download.hidden = false;
  });
start.addEventListener('click', () => recorder.start({audio:document.querySelector('#audio').checked,
  mic:document.querySelector('#mic').checked, camera:document.querySelector('#camera').checked}));
stop.addEventListener('click', () => recorder.stop());
window.addEventListener('beforeunload', event => {
  if (recorder.state !== 'idle' || downloadUrl) { event.preventDefault(); event.returnValue = ''; }
});
window.addEventListener('pagehide', () => recorder.stop());
