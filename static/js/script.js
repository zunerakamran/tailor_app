let orderId;
document.addEventListener("DOMContentLoaded", () => {
    //search order
    const input = document.getElementById("searchOrderInput");
    const table = document.getElementById("ordersTable");
    const tbody = table.querySelector("tbody");
    const rows = tbody.getElementsByTagName("tr");
    const noRecordsRow = document.getElementById("noRecordsRow");

    input.addEventListener("input", function() {  // triggers on typing or clearing
        const filter = input.value.toLowerCase();
        let visibleCount = 0;

        for (let i = 0; i < rows.length; i++) {
            // Skip the "No records" row
            if (rows[i].id === "noRecordsRow") continue;

            const nameCell = rows[i].cells[2].textContent.toLowerCase();
            const phoneCell = rows[i].cells[3].textContent.toLowerCase();

            if (nameCell.includes(filter) || phoneCell.includes(filter)) {
                rows[i].style.display = "";
                visibleCount++;
            } else {
                rows[i].style.display = "none";
            }
        }

        // Show "No records found" if no rows are visible
        noRecordsRow.style.display = visibleCount === 0 ? "" : "none";
    });
    
    const imageContainerBox = document.getElementById("image-container");
    const updateOrderForm= document.getElementById("update-order-form");
    if (!imageContainerBox) return;
    //get id of order for home page
    orderId= imageContainer.dataset.id
    // Get previous images from data attribute for update page
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

        if (res.redirected) {
            window.location.href = res.url;
        } else if (res.ok) {
            window.location.reload();
        } else {
            console.error("Update failed");
        }
    })
});

const addOrderForm = document.getElementById("add-order-form")
const imageContainer = document.getElementById("image-container");
const addBtn = document.getElementById('add-btn');
const mobileFileInput = document.getElementById("mobile-file-input");
const cameraModal = document.getElementById("camera-modal");
const cameraStream = document.getElementById("camera-stream");
const captureBtn = document.getElementById("capture-btn");
const closeCameraBtn = document.getElementById("close-camera");
const isMobile = /Mobi|Android/i.test(navigator.userAgent);
const mode = imageContainer ?.dataset.mode || "multiple";
let capturedFiles = []
let stream = null;
let webcamOpen = false;

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
async function createImagePreview(src, fileName) {

    if (mode === "single") {
        // 🔴 HOME PAGE behavior
        const file = capturedFiles[0];
        const formData = new FormData();
        formData.append("order_id", orderId);
        formData.append("image", file); 

        try {
            const res = await fetch("/update_image", {
                method: "POST",
                body: formData
            });
            if (res.ok) {
                window.location.reload(); // ✅ faster, no redirect processing
            } else {
                console.error("Update failed");
            }

        } catch (err) {
            console.error("API error:", err);
        }
        addBtn.style.display = "none";
        if (stream) stream.getTracks().forEach(t => t.stop());
            cameraModal.style.display = "none";
            webcamOpen = false;
    } else {
        // 🟢 ADD ORDER behavior
        const imgBox = document.createElement("div");
        imgBox.classList.add("image-preview-box");
        imgBox.style.position = "relative";

        imgBox.innerHTML = `
            <span class="delete-img-btn">&times;</span>
            <img src="${src}" alt="Captured Image">
        `;
        const lastAddBox = imageContainer.querySelector(".add-image-box:last-child");
        if (lastAddBox) {
            imageContainer.insertBefore(imgBox, lastAddBox);
        } else {
            imageContainer.appendChild(imgBox);
        }
        // Delete button event
        imgBox.querySelector(".delete-img-btn").addEventListener("click", () => {
            imgBox.remove();
            if (mode === "single") {
                addBtn.style.display = "flex"; // show + again
            }
            // Also remove from your capturedFiles array
            capturedFiles = capturedFiles.filter(f => f.name !== fileName);
        });
    }
}

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
        const file = new File([blob], `webcam-${Date.now()}.png`, { type: "image/png" });
        file.previewSrc = URL.createObjectURL(blob); // ✅ attach manually
        capturedFiles.push(file);
        createImagePreview(URL.createObjectURL(blob), file.name);
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

    if (res.redirected) {
        window.location.href = res.url;
    } else if (res.ok) {
        window.location.reload();
    } else {
        console.error("Update failed");
    }
});


