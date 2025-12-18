document.addEventListener("DOMContentLoaded", () => {
    const imageContainerBox = document.getElementById("image-container");
    const updateOrderForm= document.getElementById("update-order-form");
    if (!imageContainerBox) return;

    // Get previous images from data attribute
    const keptImages = JSON.parse(imageContainerBox.dataset.images || "[]");

    // Optional: attach delete functionality
    imageContainerBox.addEventListener("click", (e) => {
        if (e.target.classList.contains("delete-img-btn")) {
            const imgDiv = e.target.parentElement;
            imgDiv.remove();

            // Update the JS array if needed
            const imgEl = imgDiv.querySelector("img");
            const index = keptImages.findIndex(i => i.path === imgEl.src.split("/uploads/")[1]);
            if (index > -1) keptImages.splice(index, 1);

            // Update data attribute if needed
            imageContainerBox.dataset.images = JSON.stringify(keptImages);
        }
    });

    updateOrderForm.addEventListener('submit', async(e)=>{
        e.preventDefault()
        const formData= new FormData(updateOrderForm)
        keptImages.forEach(imgObj => {
            formData.append("kept_images[]", JSON.stringify(imgObj));
        });
        capturedFiles.forEach(file => formData.append("newImages[]", file));
        
        const res = await fetch(updateOrderForm.action, {
            method: updateOrderForm.method, // POST
            body: formData
        });

        // Manually follow Flask redirect
        if (res.redirected) {
            window.location.href = res.url;
        } else if (res.ok) {
        // optional: reload page or show success message
            window.location.reload();
        } else {
            console.error("Update failed");
        }
    })
});


const addOrderForm = document.getElementById("add-order-form")
const imageContainer = document.getElementById("image-container");
const addBtn = document.getElementById("add-btn");
const mobileFileInput = document.getElementById("mobile-file-input");
const cameraModal = document.getElementById("camera-modal");
const cameraStream = document.getElementById("camera-stream");
const captureBtn = document.getElementById("capture-btn");
const closeCameraBtn = document.getElementById("close-camera");
const isMobile = /Mobi|Android/i.test(navigator.userAgent);
const mode = imageContainer ?.dataset.mode || "multiple";
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
function createImagePreview(src, index) {
    const imgBox = document.createElement("div");
    imgBox.classList.add("image-preview-box");
    imgBox.style.position = "relative";

    imgBox.innerHTML = `
        <span class="delete-img-btn">&times;</span>
        <img src="${src}" alt="Captured Image">
    `;

    if (mode === "single") {
        // 🔴 HOME PAGE behavior
        imageContainer.appendChild(imgBox);
        addBtn.style.display = "none"; // hide +
    } else {
        // 🟢 ADD ORDER behavior
        const lastAddBox = imageContainer.querySelector(".add-image-box:last-child");
        if (lastAddBox) {
            imageContainer.insertBefore(imgBox, lastAddBox);
        } else {
            imageContainer.appendChild(imgBox);
        }
    }

    // Delete button event
    imgBox.querySelector(".delete-img-btn").addEventListener("click", () => {
        imgBox.remove();
        if (mode === "single") {
            addBtn.style.display = "flex"; // show + again
        }
        // Also remove from your capturedFiles array
        capturedFiles = capturedFiles.filter(f => f.previewSrc !== src);
    });
}


// ---------- Add new + box ----------
// function addNewAddBox() {
//     const newBox = document.createElement("label");
//     newBox.classList.add("add-image-box");
//     newBox.innerHTML = `<span class="plus-icon">+</span>
//         <input type="file" accept="image/*" capture="environment" multiple style="display:none;">`;

//     imageContainer.appendChild(newBox);
//     setupAddBox(newBox);
// }

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

addOrderForm.addEventListener("submit", async(e) => {
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


