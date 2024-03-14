from re import match


class RegexPosts:
    @classmethod
    def verify_title(cls, title: str) -> bool:
        return bool(
            match(
                pattern=r'^.{30,100}$',
                string=title
            )
        )

    @classmethod
    def verify_content(cls, content: str) -> bool:
        return bool(
            match(
                pattern=r'^.{200,5000}$',
                string=content
            )
        )
