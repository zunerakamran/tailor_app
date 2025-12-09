from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime
app = Flask(__name__)

# Database setup (SQLite example)
basedir = os.path.abspath(os.path.dirname(__file__))
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

@app.route('/add_order', methods=['GET', 'POST'])
def add_order():
    if request.method == 'POST':
        # Get form data
        customer_name = request.form['customer_name']
        phone = request.form['phone']
        address = request.form['address']
        order_for = request.form['order_for']
        order_type = request.form['order_type']
        notes = request.form['notes']

        # Handle image upload
        image_file = request.files['image']
        if image_file:
            image_path = os.path.join('static/uploads', image_file.filename)
            image_file.save(image_path)
        else:
            image_path = None

        # Create new order object
        new_order = Order(
            customer_name=customer_name,
            phone=phone,
            address=address,
            order_for=order_for,
            order_type=order_type,
            image=image_file.filename if image_file else None,
            notes=notes
        )

        # Add to database
        db.session.add(new_order)
        db.session.commit()

        return redirect(url_for('home'))

    return render_template('add_order.html')

@app.route('/view_order/<int:order_id>')
def view_order(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template('view_order.html', order=order)

if __name__ == '__main__':
    app.run(debug=True)
