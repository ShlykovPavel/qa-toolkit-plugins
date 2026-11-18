"""test_example_flow.py — шаблон многошагового (интеграционного) сценария.

Показывает, как строить сквозной тест из нескольких шагов API + проверки
состояния в БД. Все данные — локальные переменные; между тестами ничего
не передаётся.

Паттерн проверки через БД (раскомментируйте и адаптируйте под свою схему):

    from src import db_config
    from src.db_functions import DbInfo
    from src.wait_utils import wait_until

    # мгновенная проверка по известному ключу:
    with db_config.primary_session() as session:
        db_name = DbInfo.get_value_where(
            session, "resources", "name", "id", resource_id)
    assert db_name == name

    # ожидание асинхронной пропагации (вместо time.sleep):
    wait_until(
        lambda: _row_exists(resource_id),
        timeout=30,
        message=f"Запись {resource_id} не появилась в БД",
    )
"""

import allure
import pytest

from src.data_generators import generate_name
from src.example_resource.example_resource import ExampleResource

pytestmark = pytest.mark.regression


@allure.epic("Regression")
@allure.feature("ExampleFlow")
class TestExampleFlow:

    @allure.description("Полный цикл ресурса: создание → чтение → обновление → удаление")
    def test_resource_full_lifecycle(self, resource_cleaner):
        # Шаг 1. Создание (уникальное имя — обязательное условие параллельности)
        name = generate_name("flow_resource")
        resource_id = ExampleResource.create(name=name)
        resource_cleaner.append(resource_id)
        assert resource_id is not None

        # Шаг 2. Чтение и проверка данных
        resource = ExampleResource.get(resource_id)
        assert resource.name == name

        # (здесь уместна проверка состояния в БД — см. докстринг модуля)

        # Шаг 3. Обновление и проверка
        updated_name = generate_name("flow_updated")
        ExampleResource.update(resource_id, name=updated_name)
        resource = ExampleResource.get(resource_id)
        assert resource.name == updated_name

        # Шаг 4. Удаление и проверка недоступности
        ExampleResource.delete(resource_id)
        resource_cleaner.remove(resource_id)  # уже удалён — teardown не трогает
        ExampleResource.get(resource_id, status_code=404)
