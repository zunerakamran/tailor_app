let orderId, imageContainer, addBtn, mode;
let keptImages = []
const addOrderForm = document.getElementById("add-order-form")
const updateOrderForm = document.getElementById("update-order-form");
const mobileFileInput = document.getElementById("mobile-file-input");
const cameraModal = document.getElementById("camera-modal");
const cameraStream = document.getElementById("camera-stream");
const captureBtn = document.getElementById("capture-btn");
const closeCameraBtn = document.getElementById("close-camera");
const isMobile = /Mobi|Android/i.test(navigator.userAgent);

if (updateOrderForm) {
    updateOrderForm.addEventListener('submit', async (e) => {
        e.preventDefault()
        showLoader()
        const formData = new FormData(updateOrderForm)
        keptImages.forEach(imgObj => {
            formData.append("kept_images[]", JSON.stringify(imgObj));
        });
        capturedFiles.forEach(file => formData.append("newImages[]", file));

        const res = await fetch(updateOrderForm.action, {
            method: updateOrderForm.method,
            body: formData
        });

        if (res.redirected) {
            hideLoader()
            window.location.href = res.url;
        } else if (res.ok) {
            hideLoader()
            window.location.reload();
        } else {
            hideLoader()
            console.error("Update failed");
        }
    });
}
let capturedFiles = []
let stream = null;
let webcamOpen = false;
let aiScanDone = false;
let entryMode = "manual";

function isAIMode() {
    return entryMode === "ai";
}

function applyEntryModeUI() {
    const badge = document.getElementById("ai-autofill-badge");
    const banner = document.getElementById("ai-status-banner");
    const tabs = document.querySelectorAll(".entry-mode-tab");

    tabs.forEach(tab => {
        tab.classList.toggle("active", tab.dataset.entryMode === entryMode);
    });

    if (badge) {
        badge.classList.toggle("d-none", !isAIMode());
    }

    if (!isAIMode() && banner) {
        banner.classList.add("d-none");
        banner.classList.remove("d-flex");
    }
}

function setupEntryModeTabs() {
    const tabs = document.querySelectorAll(".entry-mode-tab");
    if (!tabs.length || !(addOrderForm || updateOrderForm)) return;

    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            const nextMode = tab.dataset.entryMode;
            if (!nextMode || nextMode === entryMode) return;
            entryMode = nextMode;
            if (entryMode === "ai") {
                aiScanDone = false;
            }
            applyEntryModeUI();
        });
    });

    applyEntryModeUI();
}

function maybeTriggerAIScan(file) {
    if (!(addOrderForm || updateOrderForm) || !isAIMode() || aiScanDone || !file) return;
    aiScanDone = true;
    triggerAIScan(file);
}

function openImageViewer(src) {
    let overlay = document.getElementById("image-viewer-overlay");
    if (!overlay) {
        overlay = document.createElement("div");
        overlay.id = "image-viewer-overlay";
        overlay.innerHTML = `
            <button type="button" class="image-viewer-close" aria-label="Close">&times;</button>
            <img src="" alt="Full preview">
        `;
        document.body.appendChild(overlay);
        overlay.addEventListener("click", (e) => {
            if (e.target === overlay || e.target.classList.contains("image-viewer-close")) {
                overlay.classList.remove("open");
            }
        });
        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape") overlay.classList.remove("open");
        });
    }
    overlay.querySelector("img").src = src;
    overlay.classList.add("open");
}

document.addEventListener("change", (e) => {
    if (e.target && e.target.type === "file") {
        const input = e.target;
        if (!input.files || input.files.length === 0) return;

        const container = input.closest(".image-container");
        if (container) {
            orderId = container.dataset.id;
            imageContainer = container;
            addBtn = document.getElementById(`add-btn-${orderId}`);
            mode = container.dataset.mode || "multiple";
        }

        Array.from(input.files).forEach((file, index) => {
            capturedFiles.push(file);
            const reader = new FileReader();
            reader.onload = ev => createImagePreview(ev.target.result, file.name);
            reader.readAsDataURL(file);
            // AI only reads the first image captured
            if (index === 0) {
                maybeTriggerAIScan(file);
            }
        });
        input.value = "";
    }
});

const imageConatinerByClass = document.getElementsByClassName("image-container");
Array.from(imageConatinerByClass).forEach(container => {
    container.addEventListener('click', (e) => {
        if (e.target.closest('label') || e.target.tagName.toLowerCase() === 'input') return;
        if (e.target.closest('.image-preview-box') || e.target.closest('.image-preview-box-update') || e.target.closest('.delete-img-btn')) return;
        orderId = container.dataset.id;
        imageContainer = document.getElementById(`image-container-${orderId}`);
        addBtn = document.getElementById(`add-btn-${orderId}`);
        mode = imageContainer?.dataset.mode || "multiple";
        const fileInput = imageContainer ? imageContainer.querySelector("input[type='file']") : null;
        if (fileInput) {
            fileInput.click();
        }
    });
});

const imagePreviewBoxes = document.getElementsByClassName('image-preview-box-update');
Array.from(imagePreviewBoxes).forEach(box => {
    keptImages = JSON.parse(box.dataset.images || "[]");

    const previewImg = box.querySelector("img");
    if (previewImg) {
        previewImg.style.cursor = "pointer";
        previewImg.addEventListener("click", (e) => {
            e.stopPropagation();
            openImageViewer(previewImg.src);
        });
    }

    const deleteBtn = box.querySelector(".delete-img-btn");
    if (!deleteBtn) return;

    deleteBtn.addEventListener("click", (e) => {
        e.stopPropagation();

        const imgDiv = e.target.closest(".image-preview-box-update");
        const imgEl = imgDiv.querySelector("img");
        const index = keptImages.findIndex(i => i.path === imgEl.src.split("/uploads/")[1]);

        if (index > -1) keptImages.splice(index, 1);

        imgDiv.remove();

        console.log("Updated keptImages:", keptImages);

        const parentContainer = imgDiv.closest(".image-container");
        parentContainer.dataset.images = JSON.stringify(keptImages);
    });
});

function setupAddBox(box) {
    const input = box.querySelector("input");
    if (isMobile) {
        input.addEventListener("change", () => {
            if (!input.files) return;
            Array.from(input.files).forEach((file, index) => {
                capturedFiles.push(file);
                const reader = new FileReader();
                reader.onload = ev => createImagePreview(ev.target.result, file.name);
                reader.readAsDataURL(file);
                if (index === 0) {
                    maybeTriggerAIScan(file);
                }
            });
            input.value = "";
        });
    } else {
        if (!webcamOpen) openWebcam();
    }
}

async function createImagePreview(src, fileName) {
    if (mode === "single") {
        const file = capturedFiles[0];
        const formData = new FormData();
        formData.append("order_id", orderId);
        formData.append("image", file);
        if (!isMobile) {
            if (stream) stream.getTracks().forEach(t => t.stop());
            cameraModal.style.display = "none";
            webcamOpen = false;
        }
        try {
            showLoader();
            const res = await fetch(updateImageUrl, {
                method: "POST",
                body: formData
            });

            if (res.ok) {
                hideLoader()
                window.location.reload();
            } else {
                console.error("Update failed");
                hideLoader();
            }

        } catch (err) {
            console.error("API error:", err);
            hideLoader();
        }
        addBtn.style.display = "none";
    }
    else {
        const imgBox = document.createElement("div");
        imgBox.classList.add("image-preview-box");
        imgBox.style.position = "relative";

        imgBox.innerHTML = `
            <span class="delete-img-btn">&times;</span>
            <img src="${src}" alt="Captured Image">
        `;
        const lastAddBox = imageContainer.querySelector(".add-image-box");
        if (lastAddBox) {
            imageContainer.insertBefore(imgBox, lastAddBox);
        } else {
            imageContainer.appendChild(imgBox);
        }
        imgBox.querySelector("img").style.cursor = "pointer";
        imgBox.querySelector("img").addEventListener("click", (e) => {
            e.stopPropagation();
            openImageViewer(src);
        });
        imgBox.querySelector(".delete-img-btn").addEventListener("click", (e) => {
            e.stopPropagation();
            imgBox.remove();
            if (mode === "single") {
                addBtn.style.display = "flex";
            }
            capturedFiles = capturedFiles.filter(f => f.name !== fileName);
        });
    }
}

async function openWebcam() {
    if (stream) stream.getTracks().forEach(t => t.stop());
    try {
        webcamOpen = true;
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
        cameraStream.srcObject = stream;
        await cameraStream.play();
        cameraModal.style.display = "flex";
    } catch (err) {
        alert("Cannot access webcam: " + err);
        webcamOpen = false;
        cameraModal.style.display = "none";
    }
}

if (captureBtn) {
    captureBtn.addEventListener("click", () => {
        if (!stream) return;

        const canvas = document.createElement("canvas");
        canvas.width = cameraStream.videoWidth;
        canvas.height = cameraStream.videoHeight;
        canvas.getContext("2d").drawImage(cameraStream, 0, 0);

        canvas.toBlob(blob => {
            const file = new File([blob], `webcam-${Date.now()}.png`, { type: "image/png" });
            file.previewSrc = URL.createObjectURL(blob);
            capturedFiles.push(file);
            createImagePreview(URL.createObjectURL(blob), file.name);
            maybeTriggerAIScan(file);
        }, "image/png");
    });
}

function getAIUserMessage(result, httpStatus) {
    const errorType = (result && result.error_type) || "";
    const serverError = (result && result.error) || "";
    const combined = `${errorType} ${serverError}`.toLowerCase();

    if (
        errorType === "quota" ||
        httpStatus === 429 ||
        combined.includes("quota") ||
        combined.includes("daily limit") ||
        combined.includes("resource_exhausted")
    ) {
        return {
            text: "AI daily limit reached. Please enter order details manually, or try again later.",
            alertClass: "alert-warning"
        };
    }

    if (errorType === "unavailable" || httpStatus === 401) {
        return {
            text: serverError || "AI Auto-Fill is not available right now. Please enter order details manually.",
            alertClass: "alert-warning"
        };
    }

    if (serverError) {
        return { text: serverError, alertClass: "alert-warning" };
    }

    return {
        text: "AI could not read this image. Please enter order details manually.",
        alertClass: "alert-warning"
    };
}

function setAIBannerState({ text, alertClass, showSpinner }) {
    const banner = document.getElementById("ai-status-banner");
    const statusText = document.getElementById("ai-status-text");
    const spinner = document.getElementById("ai-spinner");
    const starsIcon = document.getElementById("ai-stars-icon");
    if (!banner || !statusText) return;

    banner.classList.remove("d-none", "alert-danger", "alert-success", "alert-warning", "alert-info");
    banner.classList.add("d-flex", alertClass);
    statusText.innerText = text;

    if (showSpinner) {
        spinner.classList.remove("d-none");
        if (starsIcon) starsIcon.classList.add("d-none");
    } else {
        spinner.classList.add("d-none");
        if (starsIcon) starsIcon.classList.remove("d-none");
    }
}

async function triggerAIScan(file) {
    const banner = document.getElementById("ai-status-banner");
    const statusText = document.getElementById("ai-status-text");

    if (!banner || !statusText || (!addOrderForm && !updateOrderForm) || !isAIMode()) return;

    const currentForm = addOrderForm || updateOrderForm;

    setAIBannerState({
        text: "AI is working... Scanning your order slip image.",
        alertClass: "alert-info",
        showSpinner: true
    });

    const formData = new FormData();
    formData.append("image", file);

    const targetScanUrl = window.scanOrderImageUrl || "scan_order_image";

    try {
        const response = await fetch(targetScanUrl, {
            method: "POST",
            body: formData
        });

        let result = {};
        try {
            result = await response.json();
        } catch (_) {
            result = {};
        }

        // User may have switched back to Manual while the request was in flight
        if (!isAIMode()) {
            const bannerEl = document.getElementById("ai-status-banner");
            if (bannerEl) {
                bannerEl.classList.add("d-none");
                bannerEl.classList.remove("d-flex");
            }
            return;
        }

        if (result.success && result.data) {
            const data = result.data;
            let filledCount = 0;

            const fieldsMap = [
                { name: "order_no", val: data.order_no },
                // Missing name/phone from AI → fill '-' (never leave blank)
                { name: "name", val: data.name || "-" },
                { name: "phone", val: data.phone || "-" }
            ];

            fieldsMap.forEach(field => {
                if (field.val !== null && field.val !== undefined && field.val !== "") {
                    const inputEl = currentForm.querySelector(`[name="${field.name}"]`);
                    if (inputEl) {
                        inputEl.value = field.val;
                        inputEl.classList.remove("is-invalid");
                        inputEl.classList.add("ai-highlighted");
                        setTimeout(() => inputEl.classList.remove("ai-highlighted"), 2500);
                        filledCount++;
                    }
                }
            });

            if (filledCount > 0) {
                setAIBannerState({
                    text: `AI filled ${filledCount} field(s) from your slip. Please review and edit if needed.`,
                    alertClass: "alert-success",
                    showSpinner: false
                });
            } else {
                setAIBannerState({
                    text: "AI scanned the image but could not find clear order details. Please enter them manually.",
                    alertClass: "alert-warning",
                    showSpinner: false
                });
            }
        } else {
            const message = getAIUserMessage(result, response.status);
            setAIBannerState({
                text: message.text,
                alertClass: message.alertClass,
                showSpinner: false
            });
        }
    } catch (err) {
        console.error("AI Scan Request Error:", err);
        setAIBannerState({
            text: "AI could not connect right now. Please enter order details manually.",
            alertClass: "alert-warning",
            showSpinner: false
        });
    }
}

if (closeCameraBtn) {
    closeCameraBtn.addEventListener("click", () => {
        if (stream) stream.getTracks().forEach(t => t.stop());
        cameraModal.style.display = "none";
        webcamOpen = false;
    });
}

if (addOrderForm) {
    addOrderForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        showLoader()
        const formData = new FormData(addOrderForm);
        capturedFiles.forEach(file => formData.append("images[]", file));

        const res = await fetch(addOrderForm.action, {
            method: addOrderForm.method,
            body: formData
        });

        if (res.redirected) {
            hideLoader()
            window.location.href = res.url;
        } else if (res.ok) {
            hideLoader()
            window.location.reload();
        } else {
            hideLoader()
            console.error("Update failed");
        }
    });
}

function showLoader() {
    document.getElementById("loader-overlay").style.display = "flex";
    setTimeout(() => {
        hideLoader();
    }, 120000);
}
function hideLoader() {
    document.getElementById("loader-overlay").style.display = "none";
}

setupEntryModeTabs();
