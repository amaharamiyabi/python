from flask import Flask, render_template, request, redirect, url_for
import os
import re
import fitz  # PyMuPDF 用於生成縮略圖
import dropbox  # 用於與 Dropbox 交互
from urllib.parse import unquote

app = Flask(__name__)
CATEGORY_NAME_PATTERN = r'^[a-zA-Z0-9_\u4e00-\u9fa5 -]+$'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'txt', 'docx'}
DROPBOX_ACCESS_TOKEN = "sl.u.AFewyBsYnHZofLhEBIJJMVJOIvaKuqMiRg6C_LeXlpHF4o578_YHpwRRO5qeK_Lx4fIxMRQgujMc1X-hHgO8LHITzi9D2I4aCxkXLqHb-VxgbkrCqLWQ4q_EckdtOCmMn5WRnY6AzbVDLUFF46XAqTkB-0oseJzUnWVCr8t17cWeA5SGfHJ1LgEVp_ItrNRH74NS-IPzH7SV3TmIpPoS5yUTYs7IwsXJxOEcP68vh9pvJRNsHDecyb-JYQM0j5IM_A32Wqwvyx0ovXaxXadXWlAmyOQGCwikQqFoBaKd4IuMruddOMvf_jD2q3k9yT8tM4odXGnHU7eLbHuBEsHTXfxOULdbZhazz0Rv4NFzPeOYkCxmCFUaBuIJH8YObP0TRdrmIJCFUqt1gMfgTZJQHAXELOB1oLNtYVFncxfrK3YqrGK3NuOwYzWjUQKtXlIPwM1-hyb1fnlP3K-U6qf_vfptsELRZgxTX47gw6_AC8tbGInFcf4U28OAWADQkv3TZ-mqVc_XaFKgkTZg06w90_GxX4FA2LMtJgLvy1w4T_7KTg36o3nkYIfqrky-EseNU9dE0rtlIu3-cHluvJ1BG5Q3l0uhsclROrU_VnWgtuvEK_TBw1uuGR_JmNPls-j9pkihjmN19phpPjHiv-gmu0jDie08i4PfqfKAs6JRIIXtYnagJT_wbuFRAbkzLi2gaR4UXFgf4f7Jc4-ZmoiB_sCDWzfMOtvcNEHogGULLAkXy6ZLbM8eGGcPo3QigOhKTaK4ph7rNedu2AMvv7Cpk2zgen8FWcKnbFXsamsZPfyYfWnLs6Dq3yV1KQcf3Y-wvdw1iqzvgEqVDykLcr-mzPbFmEyaQDYgRpOEuYqRuBzHZIY_XH8Z4BuXQa5t_dsln5FK1GR88eP2YoT74Y2REmX0b7UCLQ7283j31VeLEmwCbn8TJd7-HBzteXHiV0atkz25pBQxcFl3ZSia2TQ-TjPVzoCkI7AflZQmF9Jn8cas2khJ_LQ-Tir0pDpWLfOX2eCWliia80-TBzKQ0DMKVS_NxqSfTspP5XX5ZDNhYt_JdIoZm3LUZ9D06yoqp53NgLC4INS9F3FcAJNtHQgII1ljo28tO-Ia3Kmhbl53yOm4eKdGVwfIqmDXNj0gZSv4tiPlL4LOsLt_esV0S2XH_rSOL8RCVv6EObGv388XSy6d4ddqnvxbOG8_ee5-BSV4haDQeujCDXudC8ED4EoiyNFFHL9u2lNeutJOj9L7VotSmiiftb4pcDwoUP0QjSuJKE59QxSmFV2EmTc2jpfZgNvI"  # 用您的 Dropbox Access Token 替換
DROPBOX_BASE_FOLDER = '/allianz-material'  # Dropbox 的基礎資料夾

# 初始化 Dropbox 客戶端
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

def is_valid_category_name(category):
    return re.match(CATEGORY_NAME_PATTERN, category) and '..' not in category and '/' not in category

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_to_dropbox(file, path):
    """將文件上傳到 Dropbox"""
    dbx.files_upload(file.read(), path, mode=dropbox.files.WriteMode.overwrite)

def list_dropbox_files(path):
    """列出 Dropbox 資料夾中的所有文件"""
    try:
        result = dbx.files_list_folder(path)
        return [entry.name for entry in result.entries]
    except dropbox.exceptions.ApiError:
        return []

def download_from_dropbox(path):
    """從 Dropbox 下載文件"""
    _, res = dbx.files_download(path)
    return res.content

@app.route('/')
def index():
    """首頁，顯示分類清單"""
    categories = list_dropbox_files(DROPBOX_BASE_FOLDER)
    return render_template('index.html', categories=categories)

@app.route('/category/<category>')
def view_category(category):
    """顯示分類中的文件"""
    if not is_valid_category_name(category):
        return "Invalid category name", 400

    category_path = f"{DROPBOX_BASE_FOLDER}/{category}"
    files = list_dropbox_files(category_path)
    file_urls = []
    for file in files:
        file_extension = file.rsplit('.', 1)[1].lower()
        if file_extension in {'png', 'jpg', 'jpeg'}:
            thumbnail = f"/download/{category}/{file}"
        else:
            thumbnail = "https://via.placeholder.com/150?text=FILE"
        file_urls.append({
            "name": file,
            "path": f"/download/{category}/{file}",
            "thumbnail": thumbnail
        })
    return render_template('category.html', category=category, files=file_urls)

@app.route('/upload', methods=['POST'])
def upload_file():
    """上傳文件到 Dropbox"""
    if 'file' not in request.files:
        return "No file part", 400

    file = request.files['file']
    custom_name = request.form.get('custom_name')
    category = request.form.get('category')
    new_category = request.form.get('new_category')

    # 如果選擇新增分類，使用 new_category
    if category == 'new' and new_category:
        category = new_category

    if not category or not is_valid_category_name(category):
        return "Invalid category name", 400

    filename = custom_name + f".{file.filename.rsplit('.', 1)[1].lower()}" if custom_name else file.filename
    category_path = f"{DROPBOX_BASE_FOLDER}/{category}"

    # 上傳文件到 Dropbox
    upload_to_dropbox(file, f"{category_path}/{filename}")
    return redirect(url_for('view_category', category=category))

@app.route('/download/<category>/<filename>')
def download_file(category, filename):
    """從 Dropbox 下載文件"""
    if not is_valid_category_name(category):
        return "Invalid category name", 400

    file_path = f"{DROPBOX_BASE_FOLDER}/{category}/{filename}"
    file_content = download_from_dropbox(file_path)
    return file_content

@app.route('/delete/<category>/<filename>', methods=['POST'])
def delete_file(category, filename):
    """從 Dropbox 刪除文件"""
    if not is_valid_category_name(category):
        return "Invalid category name", 400

    file_path = f"{DROPBOX_BASE_FOLDER}/{category}/{filename}"
    dbx.files_delete(file_path)
    return redirect(url_for('view_category', category=category))

@app.route('/delete_category/<category>', methods=['POST'])
def delete_category(category):
    """從 Dropbox 刪除分類資料夾"""
    if not is_valid_category_name(category):
        return "Invalid category name", 400

    category_path = f"{DROPBOX_BASE_FOLDER}/{category}"
    dbx.files_delete(category_path)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)