from datetime import date
from app.models.enums import AgeCategory


def calculate_age_category(birth_date: date) -> AgeCategory:
    """
    Calculate user's exact current age and return their age category bracket

    Args:
        birth_date: User's inputted date of birth

    Returns:
        AgeCategory: User's calculated age category bracket
    """
    # Get the current date
    today = date.today()

    age = today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )

    if 19 <= age <= 25:
        return AgeCategory.EMERGING_ADULT
    elif 26 <= age <= 32:
        return AgeCategory.EARLY_ADULT
    elif 33 <= age <= 39:
        return AgeCategory.PRIME_ADULT
    elif 40 <= age <= 46:
        return AgeCategory.MID_ADULT
    elif 47 <= age <= 53:
        return AgeCategory.MATURE_ADULT
    elif age > 53:
        return AgeCategory.SENIOR
    else:
        # Edge Case: If a user is under 19, fall back to the lowest valid bracket
        return AgeCategory.EMERGING_ADULT
