from database.initdb import db
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from database.saatler import Saatler,SaatlerPending
from database.user import User
from database.dersnotu import DersNotu
from database.degerlendirme import OgretmenDegerlendirme
from database.forum_message import ForumMessage
from database.forum_like import ForumLike
from database.kulupyonetim import KulupYonetim
from database.kulupler import Kulupler
from database.kulupicerik import Kulupicerik
from database.kayip_esya import KayipEsya
from database.kampusten import Enstantane, EnstantaneLike
import sys
sys.path.append('..')
from backend import app

with app.app_context():
    db.create_all()
    print("Tablolar başarıyla oluşturuldu!")
