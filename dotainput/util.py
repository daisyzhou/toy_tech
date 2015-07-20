import http


def create_steamapi_connection():
    return http.client.HTTPConnection(
        "api.steampowered.com",
        timeout=10
    )
