document.addEventListener("DOMContentLoaded", () => {
    updateOrderForm.addEventListener('submit', async(e)=>{
        e.preventDefault()
        showLoader()
        const formData= new FormData(updateOrderForm)
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
    })
})

let orderId, imageContainer, addBtn, mode;
let keptImages= []
const addOrderForm = document.getElementById("add-order-form")
const updateOrderForm= document.getElementById("update-order-form");
const mobileFileInput = document.getElementById("mobile-file-input");
const cameraModal = document.getElementById("camera-modal");
const cameraStream = document.getElementById("camera-stream");
const captureBtn = document.getElementById("capture-btn");
const closeCameraBtn = document.getElementById("close-camera");
const isMobile = /Mobi|Android/i.test(navigator.userAgent);
let capturedFiles = []
let stream = null;
let webcamOpen = false;
const imageConatinerByClass = document.getElementsByClassName('image-container')

Array.from(imageConatinerByClass).forEach(container => {
    container.addEventListener('click', () => {
        orderId = container.dataset.id; 
        imageContainer = document.getElementById(`image-container-${orderId}`);
        addBtn = document.getElementById(`add-btn-${orderId}`);
        mode = imageContainer ?.dataset.mode || "multiple";
        console.log(keptImages)
        if (isMobile) {
            const mobileInput = document.createElement("input");
            mobileInput.type = "file";
            mobileInput.accept = "image/*";
            mobileInput.capture = "environment";
            mobileInput.multiple = true;
            mobileInput.style.display = "none";
            addBtn.appendChild(mobileInput);
         }
        setupAddBox(addBtn)
    });
});

const imagePreviewBoxes = document.getElementsByClassName('image-preview-box-update');
Array.from(imagePreviewBoxes).forEach(box => {
     keptImages = JSON.parse(box.dataset.images || "[]");

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
            Array.from(input.files).forEach(file => {
                capturedFiles.push(file); 
                const reader = new FileReader();
                reader.onload = ev => createImagePreview(ev.target.result);
                reader.readAsDataURL(file);
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
        if(!isMobile){
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
    }, "image/png");
});

closeCameraBtn.addEventListener("click", () => {
    if (stream) stream.getTracks().forEach(t => t.stop());
    cameraModal.style.display = "none";
    webcamOpen = false;
});

addOrderForm.addEventListener("submit", async(e) => {
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

function showLoader() {
    document.getElementById("loader-overlay").style.display = "flex";
    setTimeout(() => {
        hideLoader();
    }, 120000);
}
function hideLoader() {
    document.getElementById("loader-overlay").style.display = "none";
}
