from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from PIL import Image
import os
import json
from io import BytesIO
# from googleapiclient.discovery import build
# from googleapiclient.http import MediaIoBaseUpload
# from google.oauth2 import service_account
# from io import BytesIO

app = Flask(__name__)

# SCOPES = ['https://www.googleapis.com/auth/drive.file']
# SERVICE_ACCOUNT_FILE = 'service_account.json'

# credentials = service_account.Credentials.from_service_account_file(
#     SERVICE_ACCOUNT_FILE, scopes=SCOPES
# )

# drive_service = build('drive', 'v3', credentials=credentials)
# Optional: folder ID in Google Drive where images should go
# DRIVE_FOLDER_ID = '1ebf6aRAr_vokNlek3y2E-lMSul09bqu6'

basedir = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'orders.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)       # #ID
    date = db.Column(db.DateTime, default=datetime.utcnow)  # Date
    name = db.Column(db.String(50), nullable=False)  # Customer Name
    phone = db.Column(db.String(20), nullable=False)  # Phone
    address = db.Column(db.String(100), nullable=False)  # Address
    order_for = db.Column(db.String(50), nullable=False)  # Order For
    order_type = db.Column(db.String(50), nullable=False)  # Order Type
    details = db.Column(db.Text) 
    notes = db.Column(db.String(200))  # Notes

    def __repr__(self):
        return f'<Order {self.id} - {self.customer_name}>'

def compress_to_webp(image_file, output_path, max_size_kb=200):
    img = Image.open(image_file)

    # Convert PNG → RGB to allow WebP saving
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    quality = 95  # Start high-quality

    while quality > 20:
        buffer = BytesIO()
        img.save(buffer, format="WEBP", quality=quality, method=6)
        size_kb = len(buffer.getvalue()) / 1024

        if size_kb <= max_size_kb:
            with open(output_path, "wb") as f:
                f.write(buffer.getvalue())

        quality -= 5  # reduce quality slowly
    
    # If nothing worked (rare)
    buffer = BytesIO()
    img.save(buffer, format="WEBP", quality=25, method=6)
    with open(output_path, "wb") as f:
        f.write(buffer.getvalue())


# def upload_to_drive(file_storage_obj, folder_id=None):
#     """
#     Uploads a Flask FileStorage object directly to Google Drive.
#     """
#     file_stream = BytesIO()
#     file_storage_obj.save(file_stream)
#     file_stream.seek(0)

#     file_metadata = {'name': file_storage_obj.filename}
#     if folder_id:
#         file_metadata['parents'] = [folder_id]

#     media = MediaIoBaseUpload(file_stream, mimetype=file_storage_obj.mimetype)
#     uploaded_file = drive_service.files().create(
#         body=file_metadata,
#         media_body=media,
#         fields='id, name'
#     ).execute()

#     print(f"Uploaded to Drive: {uploaded_file['name']} (ID: {uploaded_file['id']})")
#     return uploaded_file


@app.route('/')
def home():
    # Detect if the user is on a mobile device
    user_agent = request.headers.get("User-Agent", "")
    is_mobile = "Mobile" in user_agent

    # Fetch all orders
    orders = Order.query.all()

    # Process images for each order
    for order in orders:
        if order.details:
            try:
                order.images_list = json.loads(order.details)  # Load JSON array of images
                order.last_image = order.images_list[-1]['path'] if order.images_list else None
            except (ValueError, KeyError, TypeError):
                order.images_list = []
                order.last_image = None
        else:
            order.images_list = []
            order.last_image = None

    # Render the appropriate template
    template = "home_mobile.html" if is_mobile else "home.html"
    return render_template(template, orders=orders)


@app.route('/add_order', methods=['GET', 'POST'])
def add_order():
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        address = request.form.get('address')
        order_for = request.form.get('order_for')
        order_type = request.form.get('order_type')
        notes = request.form.get('notes')

        print("Customer Name:", name)
        print("Phone:", phone)
        print("Address:", address)
        print("Order For:", order_for)
        print("Order Type:", order_type)
        print("Notes:", notes)

        # Handle multiple image uploads
        images = request.files.getlist('images[]')
        image_details = []

        # for image_file in images:
        #     if image_file and image_file.filename != '':
        #         uploaded_file = upload_to_drive(image_file, folder_id=DRIVE_FOLDER_ID)
        #         image_paths.append(uploaded_file['id'])
        for image_file in images:
            if image_file and image_file.filename != '':

                filename = image_file.filename.rsplit('.', 1)[0] + ".webp"
                save_path = os.path.join(UPLOAD_FOLDER, filename)

                compress_to_webp(image_file, save_path)
                image_details.append({
                    "path": filename,
                    "uploaded_at": datetime.now().isoformat()
                })
                    

        # # Create new order object
        new_order = Order(
            name=name,
            phone=phone,
            address=address,
            order_for=order_for,
            order_type=order_type,
            details=json.dumps(image_details),
            notes=notes
        )

        # # Add to database
        db.session.add(new_order)
        db.session.commit()

        return {"success": True, "uploaded": len(image_details)}

    return render_template('add_order.html')

@app.route('/view_order/<int:order_id>')
def view_order(order_id):
    order = Order.query.get_or_404(order_id)
    
    # Load images from JSON
    images = json.loads(order.details) if order.details else []

    # Sort images by uploaded_at descending (recent first)
    images_sorted = sorted(
        images,
        key=lambda x: datetime.fromisoformat(x['uploaded_at']),
        reverse=True
    )

    # Add a formatted date for display
    for img in images_sorted:
        dt = datetime.fromisoformat(img['uploaded_at'])
        img['uploaded_at_formatted'] = dt.strftime('%d-%m-%Y')  # Example format

    return render_template('view_order.html', order=order, images=images_sorted)

@app.route('/delete_order/<int:order_id>')
def delete_order(order_id):
    order = Order.query.get_or_404(order_id)
    try:
        # Optionally, delete associated images from 'uploads' folder
        if order.details:
            images = json.loads(order.details) 
            for img in images:
                image_path = os.path.join(app.root_path, 'static', 'uploads', img)
                if os.path.exists(image_path):
                    os.remove(image_path)

        db.session.delete(order)
        db.session.commit()

    except Exception as e:
        db.session.rollback()

    return redirect(url_for('home'))

if __name__ == '__main__':
    # app.run(debug=True)
    # app.run(host='0.0.0.0', port=5000, ssl_context='adhoc')
    app.run(host='0.0.0.0', port=5000, debug=True)
