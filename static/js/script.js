//view image in the box when user selected the image

const add_order_image_input = document.getElementById('add-order-imageInput');
const add_order_image_preview = document.getElementById('add-order-image-preview');
const add_order_image_plusIcon = document.querySelector('.add-order-image-plus-icon');
const add_order_image_box = document.getElementById('add-order-image-box');

add_order_image_input.addEventListener('change', function () {
    const file = this.files[0];

    if (file) {
        const reader = new FileReader();

        reader.onload = function (e) {
            add_order_image_preview.src = e.target.result;
            add_order_image_preview.style.display = "block";
            add_order_image_plusIcon.style.display = "none";
            add_order_image_box.style.border = "none";
        }

        reader.readAsDataURL(file);
    }
});


const imageModal = document.getElementById('imageModal')
imageModal.addEventListener('show.bs.modal', event => {
    const img = event.relatedTarget
    const src = img.getAttribute('data-image')
    const modalImg = imageModal.querySelector('#modalImage')
    modalImg.src = src
})

