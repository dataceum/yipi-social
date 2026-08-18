# ==========================================
#   APPLICATION NATIVE ENUMS (CHOICES)     #
# ==========================================
import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MODERATOR = "moderator"
    USER = "user"


class Gender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"


class AgeCategory(str, enum.Enum):
    EMERGING_ADULT = "emerging adult"
    EARLY_ADULT = "early adult"
    PRIME_ADULT = "prime adult"
    MID_ADULT = "mid-adult"
    MATURE_ADULT = "mature adult"
    SENIOR = "senior"


class ProfileStatus(str, enum.Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class RejectionReason(str, enum.Enum):
    INAPPROPRIATE_CONTENT = "inappropriate content"
    COPYRIGHT_VIOLATION = "copyright violation"
    CRIMINAL_ACTIVITY = "criminal activity"


class PostStatus(str, enum.Enum):
    PUBLISHED = "published"
    DRAFT = "draft"
    ARCHIVED = "archived"
    DELETED = "deleted"
    SUSPENDED = "suspended"


class MediaType(str, enum.Enum):
    DOCUMENT = "document"
    PHOTO = "photo"
    AUDIO = "audio"
    VIDEO = "video"


class RoomType(str, enum.Enum):
    """What kind of room this is. Drives which Room fields are meaningful —
    session/stream fields apply to the two LIVE_* types; a CHAT room just
    uses RoomMember (participants) + RoomMessage (the conversation)."""

    LIVE_AUDIO = "live_audio"
    LIVE_VIDEO = "live_video"
    CHAT = "chat"


class RoomStatus(str, enum.Enum):
    """Session state for LIVE_AUDIO / LIVE_VIDEO rooms. Unused for CHAT."""

    SCHEDULED = "scheduled"
    LIVE = "live"
    ENDED = "ended"


class RoomRole(str, enum.Enum):
    """Per-room role for a RoomMember. OWNER is set automatically for the
    user who creates the room; MODERATOR/MEMBER are assignable afterward."""

    OWNER = "owner"
    MODERATOR = "moderator"
    MEMBER = "member"


class ReportReason(str, enum.Enum):
    SPAM = "spam"
    HARASSMENT = "harassment"
    HATE_SPEECH = "hate speech"
    INAPPROPRIATE_CONTENT = "inappropriate content"
    COPYRIGHT_VIOLATION = "copyright violation"
    MISINFORMATION = "misinformation"
    OTHER = "other"


class ReportStatus(str, enum.Enum):
    PENDING = "pending"
    UNDER_REVIEW = "under review"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class AgentRole(str, enum.Enum):
    """Per-team role for an Agent. OWNER is set automatically for whichever
    agent's creation caused the team to be created; only the OWNER can add
    further agents to that team. Exactly one OWNER per team is enforced by
    a partial unique index on Agent (see team.py)."""

    OWNER = "owner"
    MEMBER = "member"


class CallDirection(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallStatus(str, enum.Enum):
    RINGING = "ringing"
    ANSWERED = "answered"
    COMPLETED = "completed"
    MISSED = "missed"
    VOICEMAIL = "voicemail"
    FAILED = "failed"
