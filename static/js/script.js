const addOrderForm = document.getElementById("add-order-form")
const imageContainer = document.getElementById("image-container");
const addBtn = document.getElementById("add-btn");
const mobileFileInput = document.getElementById("mobile-file-input");
const cameraModal = document.getElementById("camera-modal");
const cameraStream = document.getElementById("camera-stream");
const captureBtn = document.getElementById("capture-btn");
const closeCameraBtn = document.getElementById("close-camera");
const isMobile = /Mobi|Android/i.test(navigator.userAgent);
const capturedFiles = []
let stream = null;
let webcamOpen = false;

// ---------- Unified function to handle + boxes ----------
function setupAddBox(box) {
    const input = box.querySelector("input");

    if (isMobile) {

        // Handle file selection
        input.addEventListener("change", () => {
            if (!input.files) return;
            Array.from(input.files).forEach(file => {
                capturedFiles.push(file); // store file
                const reader = new FileReader();
                reader.onload = ev => createImagePreview(ev.target.result);
                reader.readAsDataURL(file);
            });
            input.value = "";
        });
    } else {
        // Desktop: clicking box opens webcam
        if (input) {
            input.remove()
        }
        box.addEventListener("click", () => {
            if (!webcamOpen) openWebcam();
        });
    }
}

// ---------- Create image preview ----------
function createImagePreview(src) {
    const imgBox = document.createElement("div");
    imgBox.classList.add("image-preview-box");
    imgBox.innerHTML = `<img src="${src}" alt="Captured Image">`;

    const lastAddBox = imageContainer.querySelector(".add-image-box:last-child");
    if (lastAddBox) {
        imageContainer.insertBefore(imgBox, lastAddBox);
    } else {
        imageContainer.appendChild(imgBox);
    }
}

// ---------- Add new + box ----------
function addNewAddBox() {
    const newBox = document.createElement("label");
    newBox.classList.add("add-image-box");
    newBox.innerHTML = `<span class="plus-icon">+</span>
        <input type="file" accept="image/*" capture="environment" multiple style="display:none;">`;

    imageContainer.appendChild(newBox);
    setupAddBox(newBox);
}

// ---------- Initialize first box ----------
if (isMobile) {
    const mobileInput = document.createElement("input");
    mobileInput.type = "file";
    mobileInput.accept = "image/*";
    mobileInput.capture = "environment";
    mobileInput.multiple = true;
    mobileInput.style.display = "none";
    addBtn.appendChild(mobileInput);
}
setupAddBox(addBtn);

// ---------- Desktop webcam functions ----------
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

captureBtn.addEventListener("click", () => {
    if (!stream) return;

    const canvas = document.createElement("canvas");
    canvas.width = cameraStream.videoWidth;
    canvas.height = cameraStream.videoHeight;
    canvas.getContext("2d").drawImage(cameraStream, 0, 0);

    canvas.toBlob(blob => {
        capturedFiles.push(new File([blob], `webcam-${Date.now()}.png`, { type: "image/png" }));
        createImagePreview(URL.createObjectURL(blob));
    }, "image/png");
});

closeCameraBtn.addEventListener("click", () => {
    if (stream) stream.getTracks().forEach(t => t.stop());
    cameraModal.style.display = "none";
    webcamOpen = false;
});

addOrderForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const formData = new FormData(addOrderForm);
    capturedFiles.forEach(file => formData.append("images[]", file));

    const res = await fetch(addOrderForm.action, {
        method: addOrderForm.method,
        body: formData
    });

    const data = await res.json();
    console.log("Form submission response:", data);
});

