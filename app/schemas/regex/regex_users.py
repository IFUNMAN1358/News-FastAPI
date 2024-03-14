from re import match


class RegexUsers:

    @classmethod
    def verify_username(cls, username: str) -> bool:
        return bool(
            match(
                pattern=r'^[a-zA-Z0-9_-]{5,20}$',
                string=username
            )
        )

    @classmethod
    def verify_password(cls, password: str) -> bool:
        return bool(
            match(
                pattern=r'^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d@$!%*#?&]{6,}$',
                string=password
            )
        )
