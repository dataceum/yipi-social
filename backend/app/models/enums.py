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
