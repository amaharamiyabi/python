from flask import Flask, render_template, request, redirect, url_for
import os
import re
import fitz  # PyMuPDF 用於生成縮略圖
import dropbox  # 用於與 Dropbox 交互
from urllib.parse import unquote

app = Flask(__name__)
CATEGORY_NAME_PATTERN = r'^[a-zA-Z0-9_\u4e00-\u9fa5 -]+$'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'txt', 'docx'}
DROPBOX_ACCESS_TOKEN = "sl.CE29ox1AqcN8KeZx7kXSGVdt9ENQKztXpUUkIaA5yggTZHSwbxsRG80PVaLE6yAfdNXo75HPvvR9XpHAmKMFAAbgFC_jIw3iSOUSNfGz6EhxEFZvr0FVUUN_HuA8NOAANR5YGv3sx6N6"  # 用您的 Dropbox Access Token 替換
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

def is_valid_category_name(category):
    return re.match(CATEGORY_NAME_PATTERN, category) and '..' not in category and '/' not in category

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_to_dropbox(file, category, filename):
    """將檔案上傳到 Dropbox 並存到 '安聯' 資料夾"""
    dropbox_path = f"/安聯/{category}/{filename}"  # 確保檔案儲存在 '安聯' 資料夾下
    dbx.files_upload(file.read(), dropbox_path, mode=dropbox.files.WriteMode("overwrite"))
    shared_link = dbx.sharing_create_shared_link_with_settings(dropbox_path)
    return shared_link.url.replace('?dl=0', '?raw=1')  # 確保連結可直接訪問

@app.route('/')
def index():
    # 假設有分類資料夾可以從 Dropbox 獲取資料
    try:
        response = dbx.files_list_folder("")
        categories = [entry.name for entry in response.entries if isinstance(entry, dropbox.files.FolderMetadata)]
    except dropbox.exceptions.ApiError as e:
        categories = []
    return render_template('index.html', categories=categories)

@app.route('/category/<category>')
def view_category(category):
    if not is_valid_category_name(category):
        return "Invalid category name", 400

    # 獲取該分類資料夾內的所有檔案
    try:
        response = dbx.files_list_folder(f"/{category}")
        files = []
        for entry in response.entries:
            if isinstance(entry, dropbox.files.FileMetadata):
                file_url = dbx.sharing_create_shared_link_with_settings(entry.path_lower).url.replace('?dl=0', '?raw=1')
                file_extension = entry.name.rsplit('.', 1)[1].lower()
                if file_extension == 'pdf':
                    thumbnail = file_url  # 暫無縮略圖處理
                elif file_extension in {'png', 'jpg', 'jpeg'}:
                    thumbnail = file_url
                else:
                    thumbnail = "https://via.placeholder.com/150?text=FILE"
                files.append({"name": entry.name, "path": file_url, "thumbnail": thumbnail})
    except dropbox.exceptions.ApiError:
        return "Category not found", 404

    return render_template('category.html', category=category, files=files)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "No file part", 400

    file = request.files['file']
    custom_name = request.form.get('custom_name')
    category = request.form.get('category')
    new_category = request.form.get('new_category')

    if category == 'new' and new_category:
        category = new_category

    if not category or not is_valid_category_name(category):
        return "Invalid category name", 400

    filename = custom_name + f".{file.filename.rsplit('.', 1)[1].lower()}" if custom_name else file.filename
    dropbox_path = f"/{category}/{filename}"

    # 上傳到 Dropbox
    try:
        file_url = upload_to_dropbox(file, dropbox_path)
    except dropbox.exceptions.ApiError as e:
        return "Failed to upload file", 500

    return redirect(url_for('view_category', category=category))

@app.route('/delete/<category>/<filename>', methods=['POST'])
def delete_file(category, filename):
    if not is_valid_category_name(category):
        return "Invalid category name", 400

    dropbox_path = f"/{category}/{filename}"
    try:
        dbx.files_delete_v2(dropbox_path)
    except dropbox.exceptions.ApiError:
        return "Failed to delete file", 500

    return redirect(url_for('view_category', category=category))

@app.route('/delete_category/<category>', methods=['POST'])
def delete_category(category):
    if not is_valid_category_name(category):
        return "Invalid category name", 400

    try:
        dbx.files_delete_v2(f"/{category}")
    except dropbox.exceptions.ApiError:
        return "Failed to delete category", 500

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
