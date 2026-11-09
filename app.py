from functools import wraps
import sys
from flask import Flask, flash, render_template, request, redirect, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_
from datetime import datetime, timedelta
import os
import json
import zipfile
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from urllib.parse import quote_plus
from dotenv import load_dotenv
from PIL import Image
import time
import re

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'), override=True)
load_dotenv(override=True)

# ---------------------------------------------------------------------------
# Gemini setup — uses new google-genai package
# Run: pip install -q -U google-genai
# ---------------------------------------------------------------------------
GENAI_AVAILABLE = False

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except Exception:
    GENAI_AVAILABLE = False

# Best working free model based on server testing
GEMINI_MODEL = 'gemini-flash-latest'

app = Flask(__name__)
app.secret_key = os.getenv('DB_PASS')

user = (os.getenv("DB_USER") or "").strip()
password = (os.getenv("DB_PASS") or "").strip()
host = (os.getenv("DB_HOST") or "localhost").strip()
name = (os.getenv("DB_NAME") or "").strip()

basedir = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = \
    f"mysql+pymysql://{user}:{password}@{host}/{name}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 280
}
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB zip uploads
app.permanent_session_lifetime = timedelta(days=1)

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}
NEEDS_REVIEW_MARKER = '[NEEDS_REVIEW]'
OCR_PROMPT = (
    "You are an OCR assistant for a Pakistani tailor shop. "
    "Look at this order slip image and extract ONLY these three fields:\n"
    "- order_no: The order or slip number. Digits only (no letters). null if not visible.\n"
    "- name: Customer name exactly as written. Letters, numbers, spaces, and short codes are all allowed "
    "(e.g. Ali Hassan, Ali 12, Shop 5, A1). Do NOT reject a name just because it contains digits. "
    "null only if no name is visible.\n"
    "- phone: Pakistani mobile number only, e.g. 03001234567 or +923001234567. "
    "Must start with 03 (or +923). Digits only — no letters. "
    "CRITICAL: Dates on the slip (e.g. 15/10/2024, 15-10-24, 2024-10-15) are NOT phone numbers. "
    "If no real phone number is written on the slip, return null for phone. "
    "Never put a date, order number, or any other number into phone.\n\n"
    "IMPORTANT: If a field is not visible or unclear, use null. "
    "Never invent placeholders like XYZ, N/A, unknown, or empty strings — use null only.\n\n"
    "Reply with ONLY a raw JSON object — no markdown, no explanation, no extra text.\n"
    "Example: {\"order_no\": \"45\", \"name\": \"Ali 12\", \"phone\": \"03211234567\"}\n"
    "Example when phone missing: {\"order_no\": \"45\", \"name\": \"Ali 12\", \"phone\": null}"
)
OCR_MODELS = [
    'gemini-2.5-flash-lite',
    'gemini-3.1-flash-lite',
    'gemini-3.5-flash-lite',
    'gemini-2.5-flash',
    'gemini-3.1-flash',
    'gemini-3.5-flash',
    'gemini-3.6-flash',
    'gemini-3.7-flash',
    'gemini-3.8-flash',
    'gemini-2.5-pro',
    'gemini-3-flash-preview',
]
# Shorter list for bulk — fewer slow fallbacks, much faster when primary works
OCR_MODELS_FAST = [
    'gemini-2.5-flash-lite',
    'gemini-3.1-flash-lite',
    'gemini-3.5-flash-lite',
    'gemini-2.5-flash',
]

db = SQLAlchemy(app)

class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    name = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(100), nullable=False)
    order_for = db.Column(db.String(50), nullable=False)
    order_type = db.Column(db.String(50), nullable=False)
    details = db.Column(db.Text)
    notes = db.Column(db.String(200))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, default=1)

    def __repr__(self):
        return f'<Order {self.id} - {self.name}>'

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(512), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


def compress_to_webp(image_file, output_path,
                     max_width=1080, max_height=1080, quality=70):
    img = Image.open(image_file)
    if img.mode not in ("RGB",):
        img = img.convert("RGB")
    resample_filter = getattr(Image, 'Resampling', Image).BILINEAR
    img.thumbnail((max_width, max_height), resample_filter)
    img.save(output_path, format="WEBP", quality=quality, method=4, optimize=True)
    return os.path.getsize(output_path) / 1024


def unique_webp_filename(original_name):
    stem = os.path.splitext(os.path.basename(original_name or 'slip'))[0]
    safe_stem = re.sub(r'[^\w\-]+', '_', stem).strip('_')[:40] or 'slip'
    return f"{safe_stem}_{uuid.uuid4().hex[:8]}.webp"


def mime_from_filename(filename):
    ext = os.path.splitext(filename)[1].lower()
    return {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.webp': 'image/webp',
        '.gif': 'image/gif',
        '.bmp': 'image/bmp',
    }.get(ext, 'image/jpeg')


def is_zip_image_entry(name):
    if not name or name.endswith('/'):
        return False
    normalized = name.replace('\\', '/')
    base = os.path.basename(normalized)
    if not base or base.startswith('.'):
        return False
    if normalized.startswith('__MACOSX/') or '/__MACOSX/' in normalized:
        return False
    if '..' in normalized.split('/'):
        return False
    return os.path.splitext(base)[1].lower() in IMAGE_EXTENSIONS


def order_needs_review(order):
    return bool(order.notes and NEEDS_REVIEW_MARKER in order.notes)


def get_order_primary_image(order):
    """Return (filename, url) for the first/latest image on an order, or (None, None)."""
    if not order.details:
        return None, None
    try:
        images = json.loads(order.details)
    except Exception:
        return None, None
    if not images:
        return None, None
    try:
        images_sorted = sorted(
            images,
            key=lambda x: datetime.fromisoformat(x.get('uploaded_at', '1970-01-01')),
            reverse=True
        )
    except Exception:
        images_sorted = images
    path = images_sorted[0].get('path')
    if not path:
        return None, None
    safe = os.path.basename(path)
    return safe, url_for('static', filename=f'uploads/{safe}')


def count_needs_review_orders():
    return Order.query.filter(Order.notes.contains(NEEDS_REVIEW_MARKER)).count()


def clean_ocr_field(val):
    """Normalize OCR values — never keep placeholder text like XYZ."""
    if val is None:
        return ''
    text = str(val).strip()
    if not text:
        return ''
    if text.upper() in {'XYZ', 'N/A', 'NA', 'NULL', 'NONE', 'UNKNOWN', '-'}:
        return ''
    return text


def looks_like_date(text):
    """True if value looks like a calendar date (common OCR mix-up with phone)."""
    s = (text or '').strip()
    if not s:
        return False
    # 15/10/2024, 15-10-24, 15.10.2024
    if re.match(r'^\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}$', s):
        return True
    # 2024-10-15
    if re.match(r'^\d{4}[/.\-]\d{1,2}[/.\-]\d{1,2}$', s):
        return True
    # 15 Oct 2024 / Oct 15, 2024
    if re.search(r'(?i)\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b', s):
        return True
    digits = re.sub(r'\D', '', s)
    if re.search(r'[A-Za-z]', s):
        return False
    # Compact YYYYMMDD
    if len(digits) == 8 and digits[:4].startswith(('19', '20')):
        return True
    # Compact DDMMYYYY
    if len(digits) == 8:
        d, m, y = int(digits[:2]), int(digits[2:4]), int(digits[4:])
        if 1 <= d <= 31 and 1 <= m <= 12 and (1900 <= y <= 2100 or 0 <= y <= 99):
            return True
    # Compact DDMMYY
    if len(digits) == 6:
        d, m = int(digits[:2]), int(digits[2:4])
        if 1 <= d <= 31 and 1 <= m <= 12:
            return True
    return False


def sanitize_ocr_phone(val):
    """Keep only valid Pakistani mobiles; drop dates, letters, and other junk."""
    text = clean_ocr_field(val)
    if not text:
        return ''
    if looks_like_date(text):
        return ''
    # Any letter means this is not a phone field value
    if re.search(r'[A-Za-z]', text):
        return ''
    digits = re.sub(r'\D', '', text)
    if not digits:
        return ''
    # Normalize +92 / 92 / 3xxxxxxxxx → 03xxxxxxxxx
    if digits.startswith('92') and len(digits) == 12 and digits[2] == '3':
        digits = '0' + digits[2:]
    elif len(digits) == 10 and digits.startswith('3'):
        digits = '0' + digits
    if re.fullmatch(r'03\d{9}', digits):
        return digits
    # Not a real Pakistani mobile — leave blank (do not keep dates / short numbers)
    return ''


def sanitize_ocr_order_no(val):
    """Order number must be digits only — strip letters and other characters."""
    text = clean_ocr_field(val)
    if not text:
        return ''
    digits = re.sub(r'\D', '', text)
    return digits


def extract_order_fields_from_image(image_bytes, mime_type='image/jpeg', fast=False):
    """Run Gemini OCR on image bytes. Returns (data_dict, None) or (None, error_dict)."""
    if not GENAI_AVAILABLE:
        return None, {
            'error_type': 'unavailable',
            'error': 'AI Auto-Fill is temporarily unavailable. Please enter order details manually.',
            'status': 500
        }

    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return None, {
            'error_type': 'unavailable',
            'error': 'AI Auto-Fill is not set up yet. Please enter order details manually.',
            'status': 400
        }

    if not mime_type or not mime_type.startswith('image/'):
        mime_type = 'image/jpeg'

    models_to_try = OCR_MODELS_FAST if fast else OCR_MODELS

    try:
        client = genai.Client(api_key=api_key)
        raw_text = None
        last_error = None

        for model_name in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[
                        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                        OCR_PROMPT
                    ]
                )
                raw_text = response.text.strip()
                print(f"[OCR] Model used: {model_name}")
                break
            except Exception as model_err:
                err_str = str(model_err)
                print(f"[OCR] {model_name} failed: {err_str[:80]}")
                if '429' in err_str or 'RESOURCE_EXHAUSTED' in err_str:
                    last_error = 'quota'
                    continue
                elif '404' in err_str or 'not found' in err_str.lower():
                    last_error = 'not_found'
                    continue
                else:
                    raise model_err

        if raw_text is None:
            if last_error == 'quota':
                return None, {
                    'error_type': 'quota',
                    'error': 'AI daily limit reached. Please enter order details manually, or try again later.',
                    'status': 429
                }
            return None, {
                'error_type': 'unavailable',
                'error': 'AI could not process the image right now. Please enter order details manually.',
                'status': 500
            }

        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            lines = [l for l in lines if not l.startswith("```")]
            raw_text = "\n".join(lines).strip()

        extracted_data = json.loads(raw_text)
        # Sanitize: digits-only order_no; phone must be real PK mobile (never a date).
        # Missing name/phone → '-' so the form is never left blank.
        return {
            'order_no': sanitize_ocr_order_no(extracted_data.get('order_no')) or None,
            'name': clean_ocr_field(extracted_data.get('name')) or '-',
            'phone': sanitize_ocr_phone(extracted_data.get('phone')) or '-',
        }, None

    except json.JSONDecodeError:
        print(f"[ERROR] Could not parse response as JSON: {raw_text}")
        return None, {
            'error_type': 'parse',
            'error': 'AI read the image but could not understand the details. Please enter them manually.',
            'status': 500
        }
    except Exception as e:
        error_str = str(e)
        print(f"[ERROR] extract_order_fields_from_image: {error_str}")
        if '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str:
            return None, {
                'error_type': 'quota',
                'error': 'AI daily limit reached. Please enter order details manually, or try again later.',
                'status': 429
            }
        if 'API_KEY_INVALID' in error_str:
            return None, {
                'error_type': 'unavailable',
                'error': 'AI Auto-Fill is not available right now. Please enter order details manually.',
                'status': 401
            }
        return None, {
            'error_type': 'error',
            'error': 'AI could not scan this image. Please enter order details manually.',
            'status': 500
        }


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please login first.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


@app.after_request
def add_header(r):
    if request.path.startswith('/static/uploads/'):
        r.headers["Cache-Control"] = "public, max-age=2592000"
    else:
        r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        r.headers["Pragma"] = "no-cache"
        r.headers["Expires"] = "0"
    return r


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_or_email = request.form['username_or_email'].strip()
        password = request.form['password'].strip()
        user = User.query.filter(
            (User.username == username_or_email) | (User.email == username_or_email)
        ).first()
        if user and user.check_password(password):
            session.permanent = True
            session['user_id'] = user.id
            session['username'] = user.username
            flash(f"Welcome, {user.username}!", "success")
            return redirect(url_for('home'))
        else:
            flash("Invalid credentials!", "danger")
            return redirect(url_for('login'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for('login'))


@app.route('/')
@login_required
def home():
    user_agent = request.headers.get("User-Agent", "")
    is_mobile = "Mobile" in user_agent

    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '', type=str).strip()

    query = Order.query

    if q:
        search_term = f"%{q}%"
        query = query.filter(
            or_(
                Order.name.ilike(search_term),
                Order.phone.ilike(search_term),
                Order.order_no.ilike(search_term)
            )
        )
        from sqlalchemy import case
        relevance = case(
            (Order.order_no == q, 3),
            (Order.name == q, 3),
            (Order.phone == q, 3),
            (Order.order_no.ilike(f'{q}%'), 2),
            (Order.name.ilike(f'{q}%'), 2),
            (Order.phone.ilike(f'{q}%'), 2),
            (Order.order_no.ilike(search_term), 1),
            (Order.name.ilike(search_term), 1),
            (Order.phone.ilike(search_term), 1),
            else_=0
        )
        query = query.order_by(relevance.desc(), Order.id.desc())
    else:
        query = query.order_by(Order.id.desc())

    pagination = query.paginate(page=page, per_page=50)
    orders = pagination.items

    for order in orders:
        if order.details:
            try:
                order.images_list = json.loads(order.details)
                order.last_image = order.images_list[-1]['path'] if order.images_list else None

                for img_info in order.images_list:
                    img_path = img_info['path']
                    full_path = os.path.join(UPLOAD_FOLDER, img_path)
                    if img_path.lower().endswith('.webp'):
                        continue
                    webp_path = os.path.splitext(full_path)[0] + '.webp'
                    compress_to_webp(full_path, webp_path)
                    if os.path.exists(full_path):
                        os.remove(full_path)
                    img_info['path'] = os.path.basename(webp_path)

                order.details = json.dumps(order.images_list)
                db.session.commit()

            except Exception as e:
                print(f"[ERROR] Order {order.id}: {e}")
                order.images_list, order.last_image = [], None
        else:
            order.images_list, order.last_image = [], None

    template = "home_mobile.html" if is_mobile else "home.html"
    return render_template(
        template,
        orders=orders,
        pagination=pagination,
        q=q,
        needs_review_count=count_needs_review_orders()
    )


@app.route('/add_order', methods=['GET', 'POST'])
@login_required
def add_order():
    if request.method == 'POST':
        name = request.form.get('name')
        order_no = request.form.get('order_no')
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

        try:
            order_no_val = int(order_no) if order_no else 1
        except ValueError:
            order_no_val = 1

        new_order = Order(
            name=name,
            order_no=order_no_val,
            phone=phone,
            address=address,
            order_for=order_for,
            order_type=order_type,
            details=json.dumps(image_details),
            notes=notes,
            user_id=session.get('user_id', 1)
        )

        db.session.add(new_order)
        db.session.commit()
        return redirect(url_for('view_order', order_id=new_order.id))

    last_order = Order.query.order_by(Order.order_no.desc()).first()
    next_order_no = (last_order.order_no + 1) if last_order else 1
    return render_template('add_order.html', next_order_no=next_order_no)


# ---------------------------------------------------------------------------
# AI Image Scan — uses gemini-flash-latest (confirmed working on your server)
# ---------------------------------------------------------------------------
@app.route('/scan_order_image', methods=['POST'])
@login_required
def scan_order_image():
    if 'image' not in request.files:
        return {'success': False, 'error': 'No image provided.'}, 400

    image_file = request.files['image']
    if not image_file or image_file.filename == '':
        return {'success': False, 'error': 'Empty image file.'}, 400

    image_bytes = image_file.read()
    mime_type = image_file.content_type or mime_from_filename(image_file.filename)
    data, err = extract_order_fields_from_image(image_bytes, mime_type)
    if err:
        return {
            'success': False,
            'error_type': err.get('error_type'),
            'error': err.get('error')
        }, err.get('status', 500)

    return {'success': True, 'data': data}


# ---------------------------------------------------------------------------
# Bulk Upload — ZIP of order slip images → AI extract → create one order each
# ---------------------------------------------------------------------------
@app.route('/bulk_upload')
@login_required
def bulk_upload():
    return render_template(
        'bulk_upload.html',
        needs_review_count=count_needs_review_orders()
    )


@app.route('/needs_review')
@login_required
def needs_review():
    """Persistent list of under-review bulk orders (not yet fixed)."""
    # Fix old records where phone was wrongly saved as XYZ
    try:
        fixed = (
            Order.query
            .filter(db.func.upper(Order.phone) == 'XYZ')
            .update({Order.phone: '-'}, synchronize_session=False)
        )
        if fixed:
            db.session.commit()
            print(f"[FIX] Cleared XYZ phone on {fixed} order(s)")
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] XYZ phone cleanup: {e}")

    orders = (
        Order.query
        .filter(Order.notes.contains(NEEDS_REVIEW_MARKER))
        .order_by(Order.id.desc())
        .all()
    )
    rows = []
    for order in orders:
        image_path, image_url = get_order_primary_image(order)
        rows.append({
            'id': order.id,
            'order_no': order.order_no,
            # Show name/phone as stored; map old XYZ phone placeholder to '-'
            'name': order.name or '-',
            'phone': '-' if (order.phone or '').upper() == 'XYZ' else (order.phone or '-'),
            'image_path': image_path,
            'image_url': image_url,
            'date': order.date.strftime('%d-%m-%Y') if order.date else '',
            'notes': (order.notes or '').replace(NEEDS_REVIEW_MARKER, '').strip(),
        })
    return render_template('needs_review.html', orders=rows, total=len(rows))


@app.route('/needs_review/scan/<int:order_id>', methods=['POST'])
@login_required
def needs_review_scan(order_id):
    """Re-run AI OCR on an under-review order's image."""
    order = Order.query.get_or_404(order_id)
    image_path, _image_url = get_order_primary_image(order)
    if not image_path:
        return {'success': False, 'error': 'No image found on this order.'}, 400

    result = _scan_saved_image_result(image_path, fast=True)
    if result.get('success'):
        return {'success': True, 'data': result['data']}
    return {
        'success': False,
        'error_type': result.get('error_type'),
        'error': result.get('error') or 'AI could not read this image.'
    }, 500 if result.get('error_type') != 'quota' else 429


@app.route('/bulk_extract_zip', methods=['POST'])
@login_required
def bulk_extract_zip():
    """Unpack ZIP, save images, return list for client-side progressive AI scan."""
    if 'zip_file' not in request.files:
        return {'success': False, 'error': 'No ZIP file provided.'}, 400

    zip_file = request.files['zip_file']
    if not zip_file or zip_file.filename == '':
        return {'success': False, 'error': 'Empty ZIP file.'}, 400

    filename_lower = (zip_file.filename or '').lower()
    if not filename_lower.endswith('.zip'):
        return {'success': False, 'error': 'Please upload a .zip file containing order slip images.'}, 400

    try:
        zip_bytes = zip_file.read()
        zip_buffer = BytesIO(zip_bytes)
        if not zipfile.is_zipfile(zip_buffer):
            return {'success': False, 'error': 'Invalid ZIP file.'}, 400
        zip_buffer.seek(0)
    except Exception as e:
        print(f"[ERROR] bulk_extract_zip read: {e}")
        return {'success': False, 'error': 'Could not read the ZIP file.'}, 400

    results = []
    max_images = 2000

    try:
        with zipfile.ZipFile(zip_buffer) as zf:
            image_entries = [
                info for info in zf.infolist()
                if not info.is_dir() and is_zip_image_entry(info.filename)
            ]
            image_entries.sort(key=lambda i: i.filename.lower())

            if not image_entries:
                return {
                    'success': False,
                    'error': 'No images found in the ZIP. Add JPG/PNG/WEBP files and try again.'
                }, 400

            if len(image_entries) > max_images:
                return {
                    'success': False,
                    'error': f'Too many images ({len(image_entries)}). Please upload up to {max_images} images per ZIP.'
                }, 400

            for info in image_entries:
                source_name = os.path.basename(info.filename.replace('\\', '/'))
                item = {
                    'source_filename': source_name,
                    'image_path': None,
                    'image_url': None,
                    'order_no': '',
                    'name': '',
                    'phone': '',
                    'scan_ok': False,
                    'error': None
                }

                try:
                    image_bytes = zf.read(info)
                    webp_name = unique_webp_filename(source_name)
                    save_path = os.path.join(UPLOAD_FOLDER, webp_name)
                    compress_to_webp(BytesIO(image_bytes), save_path)
                    item['image_path'] = webp_name
                    item['image_url'] = url_for('static', filename=f'uploads/{webp_name}')
                except Exception as img_err:
                    print(f"[ERROR] bulk extract {source_name}: {img_err}")
                    item['error'] = 'Failed to extract this image.'

                results.append(item)
    except zipfile.BadZipFile:
        return {'success': False, 'error': 'Invalid or corrupted ZIP file.'}, 400
    except Exception as e:
        print(f"[ERROR] bulk_extract_zip: {e}")
        return {'success': False, 'error': 'Could not process the ZIP file.'}, 500

    return {
        'success': True,
        'total': len(results),
        'results': results
    }


def _scan_saved_image_result(image_path, fast=True):
    """Scan one saved upload file. Returns a result dict (never raises)."""
    safe_name = os.path.basename((image_path or '').strip())
    if not safe_name:
        return {
            'image_path': image_path,
            'success': False,
            'error': 'No image path provided.'
        }

    full_path = os.path.join(UPLOAD_FOLDER, safe_name)
    if not os.path.isfile(full_path):
        return {
            'image_path': safe_name,
            'success': False,
            'error': 'Image file not found.'
        }

    try:
        with open(full_path, 'rb') as f:
            image_bytes = f.read()
        mime_type = mime_from_filename(safe_name)
        data, err = extract_order_fields_from_image(image_bytes, mime_type, fast=fast)
        if data:
            return {
                'image_path': safe_name,
                'success': True,
                'data': {
                    'order_no': sanitize_ocr_order_no(data.get('order_no')),
                    'name': clean_ocr_field(data.get('name')) or '-',
                    'phone': sanitize_ocr_phone(data.get('phone')) or '-',
                }
            }
        return {
            'image_path': safe_name,
            'success': False,
            'error_type': (err or {}).get('error_type'),
            'error': (err or {}).get('error') or 'AI could not read this image.'
        }
    except Exception as e:
        print(f"[ERROR] _scan_saved_image_result: {e}")
        return {
            'image_path': safe_name,
            'success': False,
            'error': 'Failed to scan this image.'
        }


@app.route('/bulk_scan_saved_image', methods=['POST'])
@login_required
def bulk_scan_saved_image():
    """AI-scan one already-saved upload image (used for live progress)."""
    payload = request.get_json(silent=True) or {}
    image_path = (payload.get('image_path') or '').strip()
    if not image_path:
        return {'success': False, 'error': 'No image path provided.'}, 400

    result = _scan_saved_image_result(image_path, fast=True)
    if result.get('success'):
        return {'success': True, 'data': result['data']}
    status = 429 if result.get('error_type') == 'quota' else 500
    if result.get('error') == 'Image file not found.':
        status = 404
    return {
        'success': False,
        'error_type': result.get('error_type'),
        'error': result.get('error')
    }, status


@app.route('/bulk_scan_batch', methods=['POST'])
@login_required
def bulk_scan_batch():
    """Scan multiple saved images in parallel for faster bulk OCR."""
    payload = request.get_json(silent=True) or {}
    image_paths = payload.get('image_paths') or []

    if not isinstance(image_paths, list) or not image_paths:
        return {'success': False, 'error': 'No image paths provided.'}, 400

    # Cap per request to keep response time reasonable
    image_paths = [str(p).strip() for p in image_paths if p][:10]
    workers = min(6, len(image_paths))

    results_by_path = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_scan_saved_image_result, path, True): path
            for path in image_paths
        }
        for fut in as_completed(futures):
            path = futures[fut]
            try:
                results_by_path[os.path.basename(path)] = fut.result()
            except Exception as e:
                print(f"[ERROR] bulk_scan_batch item: {e}")
                results_by_path[os.path.basename(path)] = {
                    'image_path': os.path.basename(path),
                    'success': False,
                    'error': 'Failed to scan this image.'
                }

    # Preserve request order
    ordered = []
    for path in image_paths:
        key = os.path.basename(path)
        ordered.append(results_by_path.get(key) or {
            'image_path': key,
            'success': False,
            'error': 'Missing scan result.'
        })

    return {'success': True, 'results': ordered}


@app.route('/bulk_create_orders', methods=['POST'])
@login_required
def bulk_create_orders():
    payload = request.get_json(silent=True) or {}
    orders_data = payload.get('orders') or []

    if not isinstance(orders_data, list) or not orders_data:
        return {'success': False, 'error': 'No orders to create.'}, 400

    created = []
    skipped = []
    user_id = session.get('user_id', 1)
    # Track order numbers created in this request so ZIP duplicates are also skipped
    used_order_nos = set()

    last_order = Order.query.order_by(Order.order_no.desc()).first()
    next_order_no = (last_order.order_no + 1) if last_order else 1

    try:
        for raw in orders_data:
            if not isinstance(raw, dict):
                skipped.append({'reason': 'Invalid row'})
                continue

            include = raw.get('include', True)
            if not include:
                continue

            image_path = (raw.get('image_path') or '').strip()
            needs_review = bool(raw.get('needs_review'))
            name = (raw.get('name') or '').strip()
            phone = (raw.get('phone') or '').strip()
            order_no_raw = raw.get('order_no')
            order_for = (raw.get('order_for') or 'Self').strip() or 'Self'
            order_type = (raw.get('order_type') or 'Shalwar Kameez').strip() or 'Shalwar Kameez'
            address = (raw.get('address') or '').strip()
            notes = (raw.get('notes') or '').strip()
            source_filename = raw.get('source_filename')

            # Missing / placeholder name → under-review; use '-' when unknown
            if needs_review or not name or name == '-':
                needs_review = True
                if not name or name.upper() == 'XYZ':
                    name = '-'
                if NEEDS_REVIEW_MARKER not in notes:
                    notes = f"{NEEDS_REVIEW_MARKER} {notes}".strip()
            # Never store OCR/phone placeholder as XYZ — use '-'
            if phone.upper() == 'XYZ' or not phone:
                phone = '-'

            if image_path:
                safe_name = os.path.basename(image_path)
                full_path = os.path.join(UPLOAD_FOLDER, safe_name)
                if not os.path.isfile(full_path):
                    skipped.append({
                        'source': source_filename,
                        'source_filename': source_filename,
                        'image_path': safe_name,
                        'reason': 'Image file missing',
                        'duplicate': False,
                    })
                    continue
                image_path = safe_name

            try:
                if order_no_raw not in (None, ''):
                    order_no_val = int(str(order_no_raw).strip())
                    explicit_order_no = True
                else:
                    order_no_val = next_order_no
                    next_order_no += 1
                    explicit_order_no = False
            except (TypeError, ValueError):
                order_no_val = next_order_no
                next_order_no += 1
                explicit_order_no = False

            image_url = (
                url_for('static', filename=f'uploads/{image_path}') if image_path else None
            )

            # Skip if this order number already exists (DB or earlier in this ZIP)
            if explicit_order_no:
                already_in_batch = order_no_val in used_order_nos
                already_in_db = (
                    Order.query.filter_by(order_no=order_no_val).first() is not None
                )
                if already_in_batch or already_in_db:
                    skipped.append({
                        'source': source_filename,
                        'source_filename': source_filename,
                        'image_path': image_path,
                        'image_url': image_url,
                        'order_no': order_no_val,
                        'name': name,
                        'phone': phone,
                        'reason': f'Order number {order_no_val} is already created — this image was not saved',
                        'duplicate': True,
                    })
                    continue

            image_details = []
            if image_path:
                image_details.append({
                    'path': image_path,
                    'uploaded_at': datetime.now().isoformat()
                })

            new_order = Order(
                name=name[:50],
                order_no=order_no_val,
                phone=(phone or '-')[:20],
                address=(address or '-')[:100],
                order_for=order_for[:50],
                order_type=order_type[:50],
                details=json.dumps(image_details),
                notes=notes[:200] if notes else None,
                user_id=user_id
            )
            db.session.add(new_order)
            db.session.flush()  # get id before commit
            used_order_nos.add(order_no_val)
            created.append({
                'id': new_order.id,
                'order_no': order_no_val,
                'name': name,
                'phone': phone,
                'needs_review': needs_review,
                'source_filename': source_filename,
                'image_path': image_path,
                'image_url': image_url
            })

            if order_no_val >= next_order_no:
                next_order_no = order_no_val + 1

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] bulk_create_orders: {e}")
        return {'success': False, 'error': 'Failed to create orders. Please try again.'}, 500

    return {
        'success': True,
        'created_count': len(created),
        'skipped_count': len(skipped),
        'created': created,
        'skipped': skipped
    }


@app.route('/bulk_update_orders', methods=['POST'])
@login_required
def bulk_update_orders():
    """Update already-created bulk orders after manual review."""
    payload = request.get_json(silent=True) or {}
    orders_data = payload.get('orders') or []

    if not isinstance(orders_data, list) or not orders_data:
        return {'success': False, 'error': 'No orders to update.'}, 400

    updated = []
    skipped = []

    try:
        for raw in orders_data:
            if not isinstance(raw, dict):
                skipped.append({'reason': 'Invalid row'})
                continue

            order_id = raw.get('id')
            if not order_id:
                skipped.append({'reason': 'Missing order id'})
                continue

            order = Order.query.get(order_id)
            if not order:
                skipped.append({'id': order_id, 'reason': 'Order not found'})
                continue

            name = (raw.get('name') or '').strip()
            phone = (raw.get('phone') or '').strip()
            order_no_raw = raw.get('order_no')

            # Empty name not allowed — '-' is accepted when unknown
            if not name:
                skipped.append({
                    'id': order_id,
                    'reason': 'Please enter a customer name (or - if unknown)'
                })
                continue

            try:
                if order_no_raw not in (None, ''):
                    order.order_no = int(str(order_no_raw).strip())
            except (TypeError, ValueError):
                pass

            if name.upper() == 'XYZ':
                name = '-'
            order.name = name[:50]
            # Phone: use '-' when empty or old XYZ placeholder
            if phone.upper() == 'XYZ' or not phone:
                phone = '-'
            order.phone = phone[:20]

            # Clear needs-review marker once fixed
            if order.notes and NEEDS_REVIEW_MARKER in order.notes:
                cleaned = order.notes.replace(NEEDS_REVIEW_MARKER, '').strip()
                order.notes = cleaned[:200] if cleaned else None

            updated.append({'id': order.id, 'order_no': order.order_no, 'name': order.name})

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] bulk_update_orders: {e}")
        return {'success': False, 'error': 'Failed to update orders. Please try again.'}, 500

    return {
        'success': True,
        'updated_count': len(updated),
        'skipped_count': len(skipped),
        'updated': updated,
        'skipped': skipped
    }


@app.route('/view_order/<int:order_id>')
@login_required
def view_order(order_id):
    order = Order.query.get_or_404(order_id)
    images = json.loads(order.details) if order.details else []
    images_sorted = sorted(
        images,
        key=lambda x: datetime.fromisoformat(x['uploaded_at']),
        reverse=True
    )
    for img in images_sorted:
        img['uploaded_at_formatted'] = datetime.fromisoformat(img['uploaded_at']).strftime('%d-%m-%Y')
    return render_template('view_order.html', order=order, images=images_sorted)


@app.route('/delete_order/<int:order_id>')
@login_required
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
@login_required
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
        order.order_no = request.form.get('order_no')
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
        img['uploaded_at_formatted'] = datetime.fromisoformat(img['uploaded_at']).strftime('%d-%m-%Y')

    return render_template('update_order.html', order=order, images=images_sorted)


@app.route("/update_image", methods=["POST"])
@login_required
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

    order.details = json.dumps([{
        "path": filename,
        "uploaded_at": datetime.now().isoformat()
    }])
    db.session.commit()
    return redirect(url_for('home'))


@app.route('/order/<int:order_id>/gallery')
def order_gallery(order_id):
    index = int(request.args.get('index', 0))
    order = Order.query.get_or_404(order_id)
    images = json.loads(order.details) if order.details else []
    images_sorted = sorted(
        images,
        key=lambda x: datetime.fromisoformat(x['uploaded_at']),
        reverse=True
    )
    for img in images_sorted:
        img['uploaded_at_formatted'] = datetime.fromisoformat(img['uploaded_at']).strftime('%d-%m-%Y')

    return render_template('order_gallery.html', order=order, images=images_sorted, start_index=index)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)