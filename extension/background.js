// CHANGE THIS URL for production (e.g., https://yourname.pythonanywhere.com)
const SERVER_URL = "http://127.0.0.1";

chrome.runtime.onMessage.addListener(function (request, sender, sendResponse) {
    if (request.type === "save_credential") {
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
    }
});
