// activeTab grants access only after the user invokes this action.
chrome.action.onClicked.addListener(async tab => {
  try {
    const [result] = await chrome.scripting.executeScript({
      target: {tabId: tab.id}, files: ["field.js"]
    });
    if (!result.result) return;
    const field = chrome.tabs.connect(tab.id, {documentId: result.documentId, name: result.result});
    const host = chrome.runtime.connectNative("local.desktop_dictation.field");
    host.onMessage.addListener(message => {
      if (message.ready) {
        chrome.action.setBadgeText({tabId: tab.id, text: "ON"});
      } else {
        field.postMessage(message);
      }
    });
    field.onMessage.addListener(message => host.postMessage(message));
    host.onDisconnect.addListener(() => {
      chrome.action.setBadgeText({tabId: tab.id, text: ""}).catch(() => {});
      field.disconnect();
    });
    field.onDisconnect.addListener(() => host.disconnect());
  } catch (error) {
    console.warn("Could not arm this field", error.message);
  }
});
