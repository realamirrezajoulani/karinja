from fastapi import HTTPException


def validate_password_value(value: str) -> str | HTTPException:
    if len(value) < 16:
        raise HTTPException(status_code=400, detail="گذرواژه باید بیشتر از 16 کاراکتر داشته باشد")

    has_upper = has_lower = has_digit = has_special = False
    special_chars = set(r"!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~ ")

    for char in value:
        if not has_upper and char.isupper():
            has_upper = True
        elif not has_lower and char.islower():
            has_lower = True
        elif not has_digit and char.isdigit():
            has_digit = True
        elif not has_special and char in special_chars:
            has_special = True

        if has_upper and has_lower and has_digit and has_special:
            break

    if not has_upper:
        raise HTTPException(status_code=400, detail="گذرواژه باید شامل حداقل یک حرف کوچک انگلیسی باشد")
    if not has_lower:
        raise HTTPException(status_code=400, detail="گذرواژه باید شامل حداقل یک حرف بزرگ انگلیسی باشد")
    if not has_digit:
        raise HTTPException(status_code=400, detail="گذرواژه باید شامل حداقل یک عدد انگلیسی باشد")
    if not has_special:
        raise HTTPException(
            status_code=400,
            detail="گذرواژه باید شامل حداقل یک کاراکتر خاص باشد"
        )

    return value
