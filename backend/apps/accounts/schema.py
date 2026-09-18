from drf_spectacular.extensions import OpenApiAuthenticationExtension


class GuestTokenAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "apps.accounts.authentication.GuestTokenAuthentication"
    name = "GuestTokenAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "X-Guest-Token",
            "description": "POST /api/v1/guest/session ile alınan kısa ömürlü misafir token'ı.",
        }
