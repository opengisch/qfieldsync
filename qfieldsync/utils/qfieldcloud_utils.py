import requests
from urllib.parse import urljoin


def login(base_url, username, password):
    """Return the token or None if the request was not successful"""

    url = urljoin(base_url, 'api/v1/auth/login/')
    print('{} {}'.format(base_url, url))
    data = {
        "username": username,
        "password": password,
    }

    try:
        response = requests.post(
            url,
            data=data,
        )

        # Raise exception if bad response status
        response.raise_for_status()
    except requests.exceptions.RequestException:
        return None

    return response.json()['token']
