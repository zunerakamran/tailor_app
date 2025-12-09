const imageContainer = document.getElementById("image-container");
const addBtn = document.getElementById("add-btn");

const cameraModal = document.getElementById("camera-modal");
const cameraStream = document.getElementById("camera-stream");
const captureBtn = document.getElementById("capture-btn");
const closeCameraBtn = document.getElementById("close-camera");

const isMobile = /Mobi|Android/i.test(navigator.userAgent);

let stream = null;
let webcamOpen = false;

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

// ---------- Setup + box ----------
function setupAddBox(box) {
    if (isMobile) {
        const input = box.querySelector("input");
        if (!input) console.error("error");

        box.addEventListener("click", () => input.click());

        input.addEventListener("change", () => {
            if (!input.files || input.files.length === 0) console.error("error");

            Array.from(input.files).forEach(file => {
                const reader = new FileReader();
                reader.onload = (ev) => createImagePreview(ev.target.result);
                reader.readAsDataURL(file);
            });

            input.remove(); // remove used input
            addNewAddBox(); // create new + box with fresh input
        });
    } else {
        // Desktop: open webcam modal
        box.addEventListener("click", (e) => {
            e.preventDefault();
            if (!webcamOpen) openWebcam();
        });
    }
}

// ---------- Add new + box ----------
function addNewAddBox() {
    const newBox = document.createElement("label");
    newBox.classList.add("add-image-box");
    newBox.innerHTML = `<span class="plus-icon">+</span>`;

    if (isMobile) {
        // Add a new input for mobile
        const input = document.createElement("input");
        input.type = "file";
        input.accept = "image/*";
        input.capture = "environment";
        input.style.display = "none";
        newBox.appendChild(input);
    }

    imageContainer.appendChild(newBox);
    setupAddBox(newBox);
}

// ---------- Desktop webcam ----------
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

// ---------- Capture webcam image ----------
captureBtn.addEventListener("click", () => {
    if (!stream) return;

    const canvas = document.createElement("canvas");
    canvas.width = cameraStream.videoWidth;
    canvas.height = cameraStream.videoHeight;
    canvas.getContext("2d").drawImage(cameraStream, 0, 0);

    createImagePreview(canvas.toDataURL("image/png"));
});

// ---------- Close webcam ----------
closeCameraBtn.addEventListener("click", () => {
    if (stream) stream.getTracks().forEach(t => t.stop());
    cameraModal.style.display = "none";
    webcamOpen = false;
});

// ---------- Initialize first + box ----------
setupAddBox(addBtn);
