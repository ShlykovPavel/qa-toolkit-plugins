"""test_example_smoke.py — шаблон smoke-тестов.

Smoke-тесты — быстрые проверки живости. Каждый тест обязан быть:
  - быстрым (без тяжёлой подготовки)
  - НЕЗАВИСИМЫМ: не полагаться на данные, созданные другим тестом.
    Порядок выполнения и параллельный прогон (pytest-xdist) не должны
    ничего ломать. Нужен ресурс — возьмите фикстуру smoke_resource.
  - сфокусированным на самом критичном happy-path

Скопируйте файл и замените ExampleFeature на свою фичу.
"""

import allure
import pytest

from src.data_generators import generate_name
from src.example_auth import ExampleAuth
from src.example_resource.example_resource import ExampleResource

pytestmark = pytest.mark.smoke


@allure.epic("Smoke")
@allure.feature("ExampleFeature")
class TestExampleSmoke:

    @allure.description("Админ может создать ресурс, API возвращает id")
    def test_create_resource(self, resource_cleaner):
        resource_id = ExampleResource.create(name=generate_name("smoke"))
        resource_cleaner.append(resource_id)
        assert resource_id is not None

    @allure.description("Админ может получить созданный ресурс")
    def test_get_resource(self, smoke_resource):
        resource = ExampleResource.get(smoke_resource)
        assert resource.id == smoke_resource

    @allure.description("Админ может обновить ресурс")
    def test_update_resource(self, smoke_resource):
        updated_name = generate_name("smoke_updated")
        ExampleResource.update(smoke_resource, name=updated_name)
        resource = ExampleResource.get(smoke_resource)
        assert resource.name == updated_name

    @allure.description("Админ может удалить ресурс")
    def test_delete_resource(self, resource_cleaner):
        resource_id = ExampleResource.create(name=generate_name("smoke_to_delete"))
        resource_cleaner.append(resource_id)
        ExampleResource.delete(resource_id)
        resource_cleaner.remove(resource_id)  # уже удалён — teardown не трогает
        ExampleResource.get(resource_id, status_code=404)

    @allure.description("Авторизация: логин и обновление токена работают")
    def test_auth_flow(self):
        auth = ExampleAuth.login_as_admin()
        access_token = auth.get("accessToken")
        refresh_token = auth.get("refreshToken")
        assert access_token is not None

        refreshed = ExampleAuth.refresh_token(access_token, refresh_token)
        assert refreshed.get("accessToken") is not None
