# backend.py
import os
from flask import Flask, send_from_directory, jsonify
from config import (
    DATABASE_URI, SECRET_KEY, MAX_CONTENT_LENGTH,
    NOTES_UPLOAD_FOLDER, PAZAR_UPLOAD_FOLDER, KULUP_UPLOAD_FOLDER,
    DEBUG, HOST, PORT, MAIL_SERVER, MAIL_PORT, MAIL_USE_TLS, MAIL_USERNAME, MAIL_PASSWORD, MAIL_DEFAULT_SENDER
)

from database.initdb import db
from extensions import mail

# Blueprint'ler
from routes import pages
from auth import auth_bp, token_required
from api import api_bp

app = Flask(__name__)

# Config atamaları
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
app.config['UPLOAD_FOLDER'] = NOTES_UPLOAD_FOLDER
app.config['PAZAR_UPLOAD_FOLDER'] = PAZAR_UPLOAD_FOLDER
app.config['KULUP_UPLOAD_FOLDER'] = KULUP_UPLOAD_FOLDER

app.config['MAIL_SERVER'] = MAIL_SERVER
app.config['MAIL_PORT'] = MAIL_PORT
app.config['MAIL_USE_TLS'] = MAIL_USE_TLS
app.config['MAIL_USERNAME'] = MAIL_USERNAME
app.config['MAIL_PASSWORD'] = MAIL_PASSWORD
app.config['MAIL_DEFAULT_SENDER'] = MAIL_DEFAULT_SENDER

# Klasörleri oluştur
os.makedirs(NOTES_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PAZAR_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(KULUP_UPLOAD_FOLDER, exist_ok=True)

# Eklentileri başlat
db.init_app(app)
mail.init_app(app)

# Modülleri (Blueprint) sisteme kaydet
app.register_blueprint(pages)
app.register_blueprint(auth_bp)
app.register_blueprint(api_bp)

# --- DOSYA ERİŞİM ROTALARI ---
@app.route('/uploads/notes/<path:filename>', methods=['GET', 'POST'])
@token_required(next_location='/ders-notlari')
def download_note(current_user, filename):
    if current_user.kredi < 1:
        return jsonify({'message': 'Yetersiz kredi! Dosya indirmek için dosya yüklemelisiniz.'}), 403
        
    uploads = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])

    if not os.path.exists(os.path.join(uploads, filename)):
         return jsonify({'message': 'Dosya bulunamadı'}), 404
     
    try:
        current_user.kredi -= 1
        db.session.commit()
        return send_from_directory(uploads, filename)
    except Exception as e:
        current_user.kredi += 1
        db.session.commit()
        return jsonify({'message': 'İndirme sırasında hata oluştu'}), 500

@app.route('/uploads/pazar/<path:filename>')
def pazar_gorsel_indir(filename):
    return send_from_directory(os.path.join(app.root_path, app.config['PAZAR_UPLOAD_FOLDER']), filename)

@app.route('/uploads/kulup/<path:filename>')
def kulup_gorsel_indir(filename):
    return send_from_directory(os.path.join(app.root_path, app.config['KULUP_UPLOAD_FOLDER']), filename)

@app.route('/uploads/kayip/<path:filename>')
def kayip_gorsel_indir(filename):
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], 'kayip'), filename)

@app.route('/uploads/enstantane/<path:filename>')
def enstantane_gorsel_indir(filename):
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], 'enstantane'), filename)

@app.route('/sw.js')
def sw():
    return send_from_directory('static', 'sw.js', mimetype='application/javascript')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'kedi.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/uploads/katkida/<path:filename>')
def katkida_gorsel_indir(filename):
    return send_from_directory(os.path.join(app.root_path, 'uploads', 'katkida'), filename)

if __name__ == '__main__':
    app.run(host=HOST, port=PORT, debug=DEBUG)