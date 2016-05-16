import json
from requests_oauthlib import OAuth2Session
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class AccessTokenUserBackend(ModelBackend):

    def authenticate(self, remote_user, access_token):

        if not remote_user or not access_token:
            return

        json_data = self.get_user_json(access_token)
        data = json.loads(json_data)

        if 'login' not in data:
            return None

        username = data['login']

        if remote_user != username:
            return None

        UserModel = get_user_model()

        user, created = UserModel._default_manager.get_or_create(**{
            UserModel.USERNAME_FIELD: username
        })

        if created:
            user.name = data['name']
            user.email = data['email']
            user.avatar = data['avatar_url']
            user.json = json_data
            user.save()

        return user

    @staticmethod
    def get_user_json(access_token):
        oauth = OAuth2Session(token={'access_token': access_token})
        response = oauth.get("https://api.github.com/user")
        return response.content.decode()
