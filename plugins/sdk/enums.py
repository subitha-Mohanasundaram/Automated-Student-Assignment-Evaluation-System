"""Plugin system enumerations."""
from enum import Enum


class AuthType(str, Enum):
    NONE    = "none"
    API_KEY = "api_key"
    OAUTH2  = "oauth2"
    BASIC   = "basic"
    BEARER  = "bearer"
    JWT     = "jwt"
    CUSTOM  = "custom"


class FieldType(str, Enum):
    STRING   = "string"
    NUMBER   = "number"
    BOOLEAN  = "boolean"
    SELECT   = "select"
    MULTI    = "multi_select"
    PASSWORD = "password"
    TEXTAREA = "textarea"
    URL      = "url"
    EMAIL    = "email"
    JSON     = "json"
    FILE     = "file"


class TriggerType(str, Enum):
    WEBHOOK  = "webhook"
    POLLING  = "polling"
    CRON     = "cron"
    REALTIME = "realtime"
    MANUAL   = "manual"
    EVENT    = "event"


class PermissionScope(str, Enum):
    READ         = "read"
    WRITE        = "write"
    DELETE       = "delete"
    ADMIN        = "admin"
    WEBHOOK      = "webhook"
    NOTIFICATION = "notification"


class PluginStatus(str, Enum):
    ACTIVE       = "active"
    INACTIVE     = "inactive"
    ERROR        = "error"
    INSTALLING   = "installing"
    UNINSTALLING = "uninstalling"
    DEPRECATED   = "deprecated"


class LifecycleEvent(str, Enum):
    INSTALL   = "install"
    UNINSTALL = "uninstall"
    ENABLE    = "enable"
    DISABLE   = "disable"
    CONFIGURE = "configure"
    TEST      = "test"
    UPGRADE   = "upgrade"
