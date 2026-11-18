"""test_example_resource.py — шаблон регрессии для CRUD-ресурса.

Показывает:
  - happy-path тесты create / read / update / delete
  - негативные тесты (404 по несуществующему id)
  - setup/teardown через фикстуры (create_resource, resource_cleaner)
  - разметку Allure (epic / feature / description)

Каждый тест независим: данные приходят из фикстур или создаются в самом
тесте, ничего не передаётся между тестами. Скопируйте файл для нового домена.
"""

import allure
import pytest

from src.data_generators import generate_name
from src.example_resource.example_resource import ExampleResource

pytestmark = pytest.mark.regression


@allure.epic("Regression")
@allure.feature("ExampleResource")
class TestExampleResourceCreate:

    @allure.description("Создание ресурса — happy path")
    def test_create_resource(self, resource_cleaner):
        resource_id = ExampleResource.create(name=generate_name("regression"))
        resource_cleaner.append(resource_id)
        assert resource_id is not None

    @allure.description("Создание ресурса — имя сохраняется корректно")
    def test_create_resource_name_persisted(self, resource_cleaner):
        name = generate_name("regression_persisted")
        resource_id = ExampleResource.create(name=name)
        resource_cleaner.append(resource_id)
        resource = ExampleResource.get(resource_id)
        assert resource.name == name


@allure.epic("Regression")
@allure.feature("ExampleResource")
class TestExampleResourceRead:

    @allure.description("Получение ресурса по id — данные корректны")
    def test_get_resource(self, create_resource):
        resource = ExampleResource.get(create_resource)
        assert resource.id == create_resource

    @allure.description("Получение по несуществующему id — 404")
    def test_get_resource_not_found(self):
        ExampleResource.get(resource_id=999999999, status_code=404)

    @allure.description("Список ресурсов содержит созданный ресурс")
    def test_get_resource_list(self, create_resource):
        response = ExampleResource.get_list()
        ids = [item.id for item in response.data or []]
        assert create_resource in ids


@allure.epic("Regression")
@allure.feature("ExampleResource")
class TestExampleResourceUpdate:

    @allure.description("Обновление имени — изменение сохраняется")
    def test_update_resource_name(self, create_resource):
        updated_name = generate_name("regression_updated")
        ExampleResource.update(create_resource, name=updated_name)
        resource = ExampleResource.get(create_resource)
        assert resource.name == updated_name

    @allure.description("Частичное обновление — меняется только указанное поле")
    def test_partial_update_resource(self, create_resource):
        patched_description = generate_name("patched_description")
        ExampleResource.partial_update(create_resource, description=patched_description)
        resource = ExampleResource.get(create_resource)
        assert resource.description == patched_description

    @allure.description("Обновление несуществующего ресурса — 404")
    def test_update_resource_not_found(self):
        ExampleResource.update(999999999, name="irrelevant", status_code=404)


@allure.epic("Regression")
@allure.feature("ExampleResource")
class TestExampleResourceDelete:

    @allure.description("Удаление ресурса — ресурс больше не доступен")
    def test_delete_resource(self, create_resource):
        ExampleResource.delete(create_resource)
        ExampleResource.get(create_resource, status_code=404)

    @allure.description("Удаление несуществующего ресурса — 404")
    def test_delete_resource_not_found(self):
        # Адаптируйте ожидаемый код под поведение вашего API (404 или 204)
        ExampleResource.delete(999999999, status_code=404)
