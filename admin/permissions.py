ROLE_DEFINITIONS = {
    "owner": {
        "label": "Owner",
        "description": "Tam sistem erişimi",
        "permissions": [
            "system.admin",
            "system.logs",
            "system.debug",
            "system.config",
            "system.db",
            "users.view",
            "users.create",
            "users.update",
            "users.delete",
            "moderation.view",
            "moderation.manage",
            "moderation.delete",
            "content.approve",
            "content.reject",
            "content.delete",
            "role.manage",
            "audit.view",
        ],
    },
    "developer": {
        "label": "Developer",
        "description": "Teknik erişim ve sistem araçları",
        "permissions": [
            "system.logs",
            "system.debug",
            "system.config",
            "system.db",
            "users.view",
            "moderation.view",
            "content.approve",
            "content.reject",
            "audit.view",
        ],
    },
    "moderator": {
        "label": "Moderator",
        "description": "İçerik ve şikayet moderasyonu",
        "permissions": [
            "moderation.view",
            "moderation.manage",
            "content.approve",
            "content.reject",
            "content.delete",
            "users.view",
        ],
    },
}

DEFAULT_PERMISSION_KEYS = sorted({
    permission
    for role in ROLE_DEFINITIONS.values()
    for permission in role["permissions"]
})
