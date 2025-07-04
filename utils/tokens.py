from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.crypto import constant_time_compare
from django.utils.http import base36_to_int


class EmailTokenGenerator(PasswordResetTokenGenerator):
    """
    Strategy object used to generate and check tokens for email verification
    without timestamp expiration. Extends PasswordResetTokenGenerator but
    removes the timestamp validation.
    """

    key_salt = "django.contrib.auth.tokens.EmailTokenGenerator"

    def check_token(self, user, token):
        """
        Check that an email verification token is correct for a given user.
        Unlike the parent class, this does not check for timestamp expiration.
        """
        if not (user and token):
            return False

        # Parse the token (same format as parent: timestamp-hash)
        try:
            ts_b36, _ = token.split("-")
        except ValueError:
            return False

        try:
            ts = base36_to_int(ts_b36)
        except ValueError:
            return False

        # Check that the timestamp/uid has not been tampered with
        # (but don't check if it's expired)
        for secret in [self.secret, *self.secret_fallbacks]:
            if constant_time_compare(
                    self._make_token_with_timestamp(user, ts, secret),
                    token,
            ):
                return True

        return False


# Create a default instance
default_email_token_generator = EmailTokenGenerator()