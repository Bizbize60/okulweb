r"""
Forum GIF/medya URL geriye donuk duzeltme scripti.

Tenor/Giphy "paylasim" linkleri (orn. https://tenor.com/xxxxx.gif) .gif ile
bitse bile aslinda HTML sayfasi dondurur; gercek medya genelde
media.tenor.com/.../xxx.mp4 veya giphyusercontent.com uzerinde olur.
Eski (hatali) validator bu linkleri oldugu gibi kaydetmisti; bu script
mevcut kayitlari yeni validator ile yeniden cozumleyip duzeltir.

Calistirma:
    cd /home/ubuntu/okulweb  (veya proje klasoru)
    python -m database.backfill_forum_gif_urls
"""
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend import app
from database.initdb import db
from database.forum_message import ForumMessage
from api import _forum_validate_gif_url


def backfill():
    with app.app_context():
        posts = ForumMessage.query.filter(ForumMessage.gif_url.isnot(None)).all()
        checked = 0
        updated = 0
        invalidated = 0

        for post in posts:
            checked += 1
            ok, new_url = _forum_validate_gif_url(post.gif_url)

            if ok and new_url and new_url != post.gif_url:
                print(f"  - UPDATE id={post.id}: {post.gif_url} -> {new_url}")
                post.gif_url = new_url
                updated += 1
            elif not ok:
                print(f"  - INVALID id={post.id}: {post.gif_url} -> temizlendi")
                post.gif_url = None
                invalidated += 1

        if updated or invalidated:
            db.session.commit()

        print(f"\nToplam kontrol edilen: {checked}")
        print(f"Duzeltilen: {updated}")
        print(f"Gecersiz sayilip temizlenen: {invalidated}")
        return 0


if __name__ == '__main__':
    raise SystemExit(backfill())
