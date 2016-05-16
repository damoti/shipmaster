import json
from requests_oauthlib import OAuth2Session
from django.contrib.auth.backends import RemoteUserBackend


class AccessTokenUserBackend(RemoteUserBackend):

    def clean_username(self, access_token):
        oauth = OAuth2Session(access_token)
        response = oauth.get("https://api.github.com/user")
        self.json = response.content.decode()
        self.user_dict = json.loads(self.json)
        return self.user_dict['login']

    def configure_user(self, user):
        user.name = self.user_dict['name']
        user.email = self.user_dict['email']
        user.avatar = self.user_dict['avatar_url']
        user.json = self.json
        return user
