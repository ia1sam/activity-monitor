function sendTab(tab, reason) {
    if (!tab || !tab.url) return;

    fetch("http://localhost:5000/url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            url: tab.url,
            title: tab.title || "",
            tabId: tab.id,
            windowId: tab.windowId,
            reason: reason
        })
    }).catch(err => console.log("Error sending URL:", err));
}

function sendActiveTab(reason, windowId = null) {
    const query = windowId === null
        ? { active: true, lastFocusedWindow: true }
        : { active: true, windowId: windowId };

    chrome.tabs.query(query, (tabs) => {
        if (tabs.length > 0) {
            sendTab(tabs[0], reason);
        }
    });
}

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (!tab.active) return;

    if (changeInfo.url || changeInfo.title || changeInfo.status === "complete") {
        chrome.windows.get(tab.windowId, (window) => {
            if (window && window.focused) {
                chrome.tabs.get(tabId, (freshTab) => {
                    sendTab(freshTab, "tabs.onUpdated");
                });
            }
        });
    }
});

chrome.tabs.onActivated.addListener((activeInfo) => {
    chrome.windows.get(activeInfo.windowId, (window) => {
        if (!window || !window.focused) return;

        chrome.tabs.get(activeInfo.tabId, (tab) => {
            sendTab(tab, "tabs.onActivated");
        });
    });
});

chrome.windows.onFocusChanged.addListener((windowId) => {
    if (windowId === chrome.windows.WINDOW_ID_NONE) return;
    sendActiveTab("windows.onFocusChanged", windowId);
});

chrome.runtime.onStartup.addListener(() => {
    sendActiveTab("runtime.onStartup");
});

chrome.runtime.onInstalled.addListener(() => {
    sendActiveTab("runtime.onInstalled");
});

sendActiveTab("service_worker_started");