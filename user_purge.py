"""Kullanıcı hesabını, bağlı satırlarla birlikte siler."""
from sqlalchemy import inspect, or_

from database.initdb import db
from database.user import User, Ambassador, Referral, UserBadge, EarnedReward
from database.forum_message import ForumMessage
from database.forum_like import ForumLike
from database.forum_comment import ForumComment
from database.kayip_esya import KayipEsya
from database.kampusten import Enstantane, EnstantaneLike
from database.subscription import WebPushSubscription
from database.dersnotu import DersNotu, DersNotuBekleyen
from database.pazar import PazarIlani
from database.degerlendirme import OgretmenDegerlendirme
from database.istek import Istek
from database.kulupicerik import Kulupicerik
from database.kulupyonetim import KulupYonetim
from database.daily_active import DailyActiveUser
from database.credit_audit import UserCreditChangeLog
from database.admin_rbac import UserRole, ModerationCase, ModerationAction, AdminAuditLog


def _tables():
    try:
        return set(inspect(db.engine).get_table_names())
    except Exception:
        return set()


def _delete_ids(model, ids):
    if not ids:
        return
    model.query.filter(model.id.in_(list(ids))).delete(synchronize_session=False)


def purge_user_account(user: User) -> None:
    """Kullanıcıyı ve ona bağlı kayıtları siler. Commit çağıran taraftadır."""
    uid = user.id
    tables = _tables()

    if 'forum_likes' in tables:
        message_ids = []
        if 'forum_messages' in tables:
            message_ids = [
                row[0] for row in db.session.query(ForumMessage.id).filter(ForumMessage.user_id == uid).all()
            ]
        like_filter = ForumLike.user_id == uid
        if message_ids:
            like_filter = or_(like_filter, ForumLike.message_id.in_(message_ids))
        ForumLike.query.filter(like_filter).delete(synchronize_session=False)

    if 'forum_comments' in tables:
        comment_filter = ForumComment.user_id == uid
        if 'forum_messages' in tables:
            owned_messages = db.session.query(ForumMessage.id).filter(ForumMessage.user_id == uid)
            comment_filter = or_(comment_filter, ForumComment.message_id.in_(owned_messages))
        comment_ids = {row[0] for row in db.session.query(ForumComment.id).filter(comment_filter).all()}
        for _ in range(12):
            if not comment_ids:
                break
            extra = {
                row[0]
                for row in db.session.query(ForumComment.id).filter(
                    ForumComment.parent_comment_id.in_(list(comment_ids))
                ).all()
            }
            new_ids = extra - comment_ids
            if not new_ids:
                break
            comment_ids |= new_ids
        _delete_ids(ForumComment, comment_ids)

    if 'forum_messages' in tables:
        ForumMessage.query.filter_by(user_id=uid).delete(synchronize_session=False)

    if 'enstantane_likes' in tables:
        photo_ids = []
        if 'enstantaneler' in tables:
            photo_ids = [row[0] for row in db.session.query(Enstantane.id).filter(Enstantane.user_id == uid).all()]
        like_filter = EnstantaneLike.user_id == uid
        if photo_ids:
            like_filter = or_(like_filter, EnstantaneLike.enstantane_id.in_(photo_ids))
        EnstantaneLike.query.filter(like_filter).delete(synchronize_session=False)
    if 'enstantaneler' in tables:
        Enstantane.query.filter_by(user_id=uid).delete(synchronize_session=False)

    if 'user_credit_change_logs' in tables:
        UserCreditChangeLog.query.filter(
            or_(UserCreditChangeLog.target_user_id == uid, UserCreditChangeLog.actor_user_id == uid)
        ).delete(synchronize_session=False)

    if 'referrals' in tables:
        Referral.query.filter(
            or_(Referral.davet_eden_id == uid, Referral.davet_edilen_id == uid)
        ).delete(synchronize_session=False)
    if 'user_badges' in tables:
        UserBadge.query.filter_by(user_id=uid).delete(synchronize_session=False)
    if 'earned_rewards' in tables:
        EarnedReward.query.filter_by(user_id=uid).delete(synchronize_session=False)
    if 'ambassadors' in tables:
        Ambassador.query.filter_by(user_id=uid).delete(synchronize_session=False)
    if 'daily_active_users' in tables:
        DailyActiveUser.query.filter_by(user_id=uid).delete(synchronize_session=False)
    if 'istekler' in tables:
        Istek.query.filter_by(user_id=uid).delete(synchronize_session=False)
    if 'kayip_esya' in tables:
        KayipEsya.query.filter_by(user_id=uid).delete(synchronize_session=False)
    if 'pazar_ilanlari' in tables:
        PazarIlani.query.filter_by(user_id=uid).delete(synchronize_session=False)
    if 'ders_notlari' in tables:
        DersNotu.query.filter_by(user_id=uid).delete(synchronize_session=False)
    if 'ders_notlari_bekleyen' in tables:
        DersNotuBekleyen.query.filter_by(user_id=uid).delete(synchronize_session=False)
    if 'ogretmen_degerlendirmeleri' in tables:
        OgretmenDegerlendirme.query.filter_by(user_id=uid).delete(synchronize_session=False)
    if 'webpush_subscriptions' in tables:
        WebPushSubscription.query.filter_by(user_id=uid).delete(synchronize_session=False)
    if 'kulup_icerik' in tables:
        Kulupicerik.query.filter_by(user_id=uid).delete(synchronize_session=False)
    if 'kulup_yonetim' in tables:
        KulupYonetim.query.filter_by(kullanici_id=uid).delete(synchronize_session=False)
    if 'user_roles' in tables:
        UserRole.query.filter_by(user_id=uid).delete(synchronize_session=False)
    if 'admin_audit_logs' in tables:
        AdminAuditLog.query.filter_by(user_id=uid).delete(synchronize_session=False)
    if 'moderation_actions' in tables:
        ModerationAction.query.filter_by(actor_user_id=uid).update(
            {ModerationAction.actor_user_id: None}, synchronize_session=False
        )
    if 'moderation_cases' in tables:
        ModerationCase.query.filter_by(reporter_user_id=uid).update(
            {ModerationCase.reporter_user_id: None}, synchronize_session=False
        )
        ModerationCase.query.filter_by(assignee_user_id=uid).update(
            {ModerationCase.assignee_user_id: None}, synchronize_session=False
        )

    db.session.delete(user)
