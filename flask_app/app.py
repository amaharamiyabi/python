from flask import Flask, render_template, request, send_from_directory, redirect, url_for
import os
import re
import shutil
import fitz  # PyMuPDF 用於生成縮略圖
from urllib.parse import unquote

app = Flask(__name__)
CATEGORY_NAME_PATTERN = r'^[a-zA-Z0-9_\u4e00-\u9fa5 -]+$'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'txt', 'docx'}
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
app.config['BASE_UPLOAD_FOLDER'] = BASE_UPLOAD_FOLDER

# 確保主目錄存在
os.makedirs(BASE_UPLOAD_FOLDER, exist_ok=True)

def is_valid_category_name(category):
    return re.match(CATEGORY_NAME_PATTERN, category) and '..' not in category and '/' not in category

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_thumbnail(pdf_path, thumbnail_path):
    doc = fitz.open(pdf_path)
    page = doc[0]
    pix = page.get_pixmap()
    os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)
    pix.save(thumbnail_path)

@app.route('/')
def index():
    categories = sorted(os.listdir(app.config['BASE_UPLOAD_FOLDER']))
    return render_template('index.html', categories=categories)

@app.route('/category/<category>')
def view_category(category):
    if not is_valid_category_name(category):
        return "Invalid category name", 400

    category_path = os.path.join(app.config['BASE_UPLOAD_FOLDER'], category)
    if not os.path.exists(category_path):
        return "Category not found", 404

    files = os.listdir(category_path)
    file_urls = []
    for file in files:
        file_extension = file.rsplit('.', 1)[1].lower()
        file_path = f"/download/{category}/{file}"
        if file_extension == 'pdf':
            thumbnail = f"/thumbnails/{category}/{file}.png"
        elif file_extension in {'png', 'jpg', 'jpeg'}:
            thumbnail = file_path  # 圖片直接作為縮略圖
        else:
            thumbnail = "https://via.placeholder.com/150?text=FILE"  # 其他文件用占位符
        file_urls.append({
            "name": file,
            "path": file_path,
            "thumbnail": thumbnail
        })
    return render_template('category.html', category=category, files=file_urls)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "No file part"

    file = request.files['file']
    custom_name = request.form.get('custom_name')
    category = request.form.get('category')
    new_category = request.form.get('new_category')

    # 如果選擇新增分類，使用 new_category
    if category == 'new' and new_category:
        category = new_category

    if not category or not is_valid_category_name(category):
        return "Invalid category name", 400

    category_path = os.path.join(app.config['BASE_UPLOAD_FOLDER'], category)
    os.makedirs(category_path, exist_ok=True)

    if file and allowed_file(file.filename):
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        filename = custom_name + f".{file_extension}" if custom_name else file.filename
        save_path = os.path.join(category_path, filename)
        file.save(save_path)

        # 如果是 PDF 文件，生成縮略圖
        if file_extension == 'pdf':
            thumbnail_path = os.path.join(BASE_DIR, 'thumbnails', category, f"{filename}.png")
            generate_thumbnail(save_path, thumbnail_path)

        return redirect(url_for('view_category', category=category))
    return "Invalid file type. Allowed types are: pdf, png, jpg, jpeg, txt, docx."

@app.route('/thumbnails/<path:filename>')
def get_thumbnail(filename):
    thumbnail_dir = os.path.join(BASE_DIR, 'thumbnails')
    return send_from_directory(thumbnail_dir, filename)

@app.route('/download/<category>/<filename>')
def download_file(category, filename):
    filename = unquote(filename)

    if not is_valid_category_name(category):
        return "Invalid category name", 400

    category_path = os.path.join(app.config['BASE_UPLOAD_FOLDER'], category)
    if not os.path.exists(category_path):
        return "Category not found", 404

    file_path = os.path.join(category_path, filename)
    if not os.path.exists(file_path):
        return "File not found", 404

    return send_from_directory(category_path, filename)

@app.route('/delete/<category>/<filename>', methods=['POST'])
def delete_file(category, filename):
    if not is_valid_category_name(category):
        return "Invalid category name", 400

    category_path = os.path.join(app.config['BASE_UPLOAD_FOLDER'], category)
    file_path = os.path.join(category_path, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        return redirect(url_for('view_category', category=category))
    return "File not found", 404

@app.route('/delete_category/<category>', methods=['POST'])
def delete_category(category):
    if not is_valid_category_name(category):
        return "Invalid category name", 400

    category_path = os.path.join(app.config['BASE_UPLOAD_FOLDER'], category)
    if not os.path.exists(category_path):
        return "Category not found", 404

    shutil.rmtree(category_path)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
