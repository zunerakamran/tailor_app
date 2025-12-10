from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime
app = Flask(__name__)

# Database setup (SQLite example)
basedir = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'orders.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)       # #ID
    date = db.Column(db.DateTime, default=datetime.utcnow)  # Date
    customer_name = db.Column(db.String(50), nullable=False)  # Customer Name
    phone = db.Column(db.String(20), nullable=False)  # Phone
    address = db.Column(db.String(100), nullable=False)  # Address
    order_for = db.Column(db.String(50), nullable=False)  # Order For
    order_type = db.Column(db.String(50), nullable=False)  # Order Type
    image = db.Column(db.Text) 
    notes = db.Column(db.String(200))  # Notes

    def __repr__(self):
        return f'<Order {self.id} - {self.customer_name}>'


@app.route('/')
def home():
    orders = Order.query.all() 
    return render_template('home.html', orders=orders)

@app.route('/test')
def test():
    return render_template('test.html')

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
        image_paths = []

        for image_file in images:
            if image_file and image_file.filename != '':
                image_path = os.path.join(UPLOAD_FOLDER, image_file.filename)
                image_file.save(image_path)
                image_paths.append(image_path)
                print("Saved image:", image_path)  # console log for each image

        # Log all uploaded images at once
        print("All uploaded images:", image_paths)

        # # Create new order object
        # new_order = Order(
        #     customer_name=customer_name,
        #     phone=phone,
        #     address=address,
        #     order_for=order_for,
        #     order_type=order_type,
        #     image=image_file.filename if image_file else None,
        #     notes=notes
        # )

        # # Add to database
        # db.session.add(new_order)
        # db.session.commit()

        return {"success": True, "uploaded": len(image_paths)}

    return render_template('add_order.html')

@app.route('/view_order/<int:order_id>')
def view_order(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template('view_order.html', order=order)

if __name__ == '__main__':
    # app.run(debug=True)
    # app.run(host='0.0.0.0', port=5000, ssl_context='adhoc')
    app.run(host='0.0.0.0', port=5000)
