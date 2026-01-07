from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from PIL import Image
import os
import json
from io import BytesIO

app = Flask(__name__)

basedir = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'orders.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)       
    date = db.Column(db.DateTime, default=datetime.utcnow)  
    name = db.Column(db.String(50), nullable=False)  
    phone = db.Column(db.String(20), nullable=False)  
    address = db.Column(db.String(100), nullable=False)  
    order_for = db.Column(db.String(50), nullable=False)  
    order_type = db.Column(db.String(50), nullable=False) 
    details = db.Column(db.Text) 
    notes = db.Column(db.String(200)) 

    def __repr__(self):
        return f'<Order {self.id} - {self.customer_name}>'

def compress_to_webp(image_file, output_path,
                     max_width=1080, max_height=1080, quality=70):
    img = Image.open(image_file)

    if img.mode not in ("RGB",):
        img = img.convert("RGB")

    img.thumbnail((max_width, max_height), Image.BILINEAR)

    img.save(
        output_path,
        format="WEBP",
        quality=quality,
        method=4,
        optimize=True
    )
    return os.path.getsize(output_path) / 1024

@app.route('/')
def home():
    user_agent = request.headers.get("User-Agent", "")
    is_mobile = "Mobile" in user_agent

    orders = Order.query.all()

    for order in orders:
        if order.details:
            try:
                order.images_list = json.loads(order.details)  
                order.last_image = order.images_list[-1]['path'] if order.images_list else None
            except (ValueError, KeyError, TypeError):
                order.images_list = []
                order.last_image = None
        else:
            order.images_list = []
            order.last_image = None

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
        images = request.files.getlist('images[]')
        image_details = []

        for image_file in images:
            if image_file and image_file.filename != '':

                filename = image_file.filename.rsplit('.', 1)[0] + ".webp"
                save_path = os.path.join(UPLOAD_FOLDER, filename)

                compress_to_webp(image_file, save_path)
                image_details.append({
                    "path": filename,
                    "uploaded_at": datetime.now().isoformat()
                })
                    
        new_order = Order(
            name=name,
            phone=phone,
            address=address,
            order_for=order_for,
            order_type=order_type,
            details=json.dumps(image_details),
            notes=notes
        )

        db.session.add(new_order)
        db.session.commit()

        return redirect(url_for('view_order', order_id=new_order.id))

    return render_template('add_order.html')

@app.route('/view_order/<int:order_id>')
def view_order(order_id):
    order = Order.query.get_or_404(order_id)
    
    images = json.loads(order.details) if order.details else []

    images_sorted = sorted(
        images,
        key=lambda x: datetime.fromisoformat(x['uploaded_at']),
        reverse=True
    )

    for img in images_sorted:
        dt = datetime.fromisoformat(img['uploaded_at'])
        img['uploaded_at_formatted'] = dt.strftime('%d-%m-%Y')  

    return render_template('view_order.html', order=order, images=images_sorted)

@app.route('/delete_order/<int:order_id>')
def delete_order(order_id):
    order = Order.query.get_or_404(order_id)
    try:
        if order.details:
            images = json.loads(order.details) 
            for img in images:
                image_path = os.path.join(app.root_path, 'static', 'uploads', img['path'])
                if os.path.exists(image_path):
                    os.remove(image_path)

        db.session.delete(order)
        db.session.commit()

    except Exception as e:
        db.session.rollback()

    return redirect(url_for('home'))

@app.route('/update_order/<int:order_id>', methods=['GET', 'POST'])
def update_order(order_id):
    order = Order.query.get_or_404(order_id)

    if request.method == 'POST':

        previous_images = json.loads(order.details) if order.details else []
        new_images = request.files.getlist('newImages[]')

        kept_images_raw = request.form.getlist('kept_images[]')
        kept_images = [json.loads(img) for img in kept_images_raw]
        kept_paths = [img['path'] for img in kept_images]

        updated_images = []

        for previousImg in previous_images:
            if previousImg['path'] not in kept_paths:
                file_path = os.path.join(UPLOAD_FOLDER, previousImg['path'])
                if os.path.exists(file_path):
                    os.remove(file_path)
            else:
                updated_images.append(previousImg)

        for image_file in new_images:
            if image_file and image_file.filename != '':

                filename = image_file.filename.rsplit('.', 1)[0] + ".webp"
                save_path = os.path.join(UPLOAD_FOLDER, filename)

                compress_to_webp(image_file, save_path)

                updated_images.append({
                    "path": filename,
                    "uploaded_at": datetime.now().isoformat()
                })

        order.details = json.dumps(updated_images)
        order.name = request.form.get('name')
        order.phone = request.form.get('phone')
        order.address = request.form.get('address')
        order.order_for = request.form.get('order_for')
        order.order_type = request.form.get('order_type')
        order.notes = request.form.get('notes')

        db.session.commit()
        return redirect(url_for('view_order', order_id=order.id))

    images = json.loads(order.details) if order.details else []

    images_sorted = sorted(
        images,
        key=lambda x: datetime.fromisoformat(x['uploaded_at']),
        reverse=True
    )

    for img in images_sorted:
        img['uploaded_at_formatted'] = datetime.fromisoformat(
            img['uploaded_at']
        ).strftime('%d-%m-%Y')

    return render_template(
        'update_order.html',
        order=order,
        images=images_sorted
    )

@app.route("/update_image", methods=["POST"])
def update_image():
    order_id = request.form.get("order_id")
    image_file = request.files.get("image")

    if not image_file:
        return {"success": False, "error": "No image provided"}, 400

    filename = image_file.filename.rsplit(".", 1)[0] + ".webp"
    save_path = os.path.join(UPLOAD_FOLDER, filename)

    compress_to_webp(image_file, save_path)

    order = Order.query.get(order_id)
    if not order:
        return {"success": False, "error": "Order not found"}, 404

    images = [{
        "path": filename,
        "uploaded_at": datetime.now().isoformat()
    }]

    # Save to database
    order.details = json.dumps(images)
    db.session.commit()

    return redirect(url_for('home'))

if __name__ == '__main__':
    # app.run(debug=True)
    # app.run(host='0.0.0.0', port=5000, ssl_context='adhoc')
    app.run(host='0.0.0.0', port=5000, debug=True)
