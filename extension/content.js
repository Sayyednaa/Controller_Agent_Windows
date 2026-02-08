document.addEventListener("change", function (event) {
    const target = event.target;
    if (target.tagName.toLowerCase() === "input") {
        const inputType = target.type.toLowerCase();
        if (inputTypesToCapture.includes(inputType)) {
            captureFormData(target.form);
        }
    }
});

const inputTypesToCapture = ["text", "email", "password"];

function captureFormData(form) {
    if (!form) return;

    let formData = {
        url: window.location.href,
        username: "",
        email: "",
        password: ""
    };

    const inputs = form.querySelectorAll("input");
    inputs.forEach(input => {
        const inputType = input.type.toLowerCase();
        if (inputType === "password") {
            formData.password = input.value;
        } else if (inputType === "email" || input.name.toLowerCase().includes("email")) {
            formData.email = input.value;
        } else if (inputType === "text" && (input.name.toLowerCase().includes("user") || input.name.toLowerCase().includes("login"))) {
            formData.username = input.value;
        }
    });

    if (formData.password) {
        chrome.runtime.sendMessage({
            type: "save_credential",
            data: formData
        });
    }
}
