import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend import app
from database.initdb import db

from database.dersnotu import DersNotu, DersNotuBekleyen
from database.user import (
    User, Ambassador, Referral, Badge, UserBadge,
    ReferralReward, EarnedReward
)
from database.kampusten import Enstantane, EnstantaneLike
from database.pazar import PazarIlani
from database.degerlendirme import OgretmenDegerlendirme
from database.forum_like import ForumLike
from database.forum_message import ForumMessage
from database.kayip_esya import KayipEsya
from database.kulupicerik import Kulupicerik
from database.kulupler import Kulupler
from database.kulupyonetim import KulupYonetim
from database.saatler import Saatler, SaatlerPending
from database.subscription import WebPushSubscription
from database.istek import Istek
from database.katkida import KatkidaBulunan
from database.moderator import Moderator
from database.daily_active import DailyActiveUser

with app.app_context():
    db.create_all()
    print("Tablolar başarıyla oluşturuldu!")
