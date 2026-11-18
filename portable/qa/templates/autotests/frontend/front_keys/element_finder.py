"""Базовый класс поиска элементов для Selenium page objects.

Принцип: не найденный элемент — немедленная ошибка с понятным сообщением
(какой селектор, какое условие ожидания), а не return None. None превращает
падение в невнятный AttributeError дальше по тесту и усложняет разбор.
"""

from typing import Literal

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

FinderType = Literal["Dom_located", "Clickable", "Visible", "Invisible"]

# Условия ожидания WebDriverWait по имени
_CONDITIONS = {
    "Dom_located": EC.presence_of_element_located,   # элемент есть в DOM
    "Clickable": EC.element_to_be_clickable,          # элемент кликабелен
    "Visible": EC.visibility_of_element_located,      # элемент видим
    "Invisible": EC.invisibility_of_element_located,  # элемент невидим/отсутствует
}

DEFAULT_WAIT_SECONDS = 10


class ButtonFinder:

    def __init__(self, driver):
        self.driver = driver

    def _find_element(self, by_type, value, finder_type: FinderType = "Dom_located"):
        """Общий метод поиска элемента.

        :param by_type: тип локатора (By.ID, By.XPATH и т.д.)
        :param value: значение локатора
        :param finder_type: условие ожидания (см. _CONDITIONS)
        """
        condition = _CONDITIONS.get(finder_type)
        if condition is None:
            raise ValueError(
                f"Неизвестный finder_type={finder_type!r}. Допустимые: {list(_CONDITIONS)}"
            )
        try:
            return WebDriverWait(self.driver, DEFAULT_WAIT_SECONDS).until(
                condition((by_type, value))
            )
        except TimeoutException:
            raise AssertionError(
                f"Элемент не найден за {DEFAULT_WAIT_SECONDS} с: "
                f"{by_type}={value!r} (условие: {finder_type})"
            )

    def find_element_by_id(self, element_id: str, finder_type: FinderType = "Dom_located"):
        return self._find_element(By.ID, element_id, finder_type)

    def find_element_by_class_name(self, class_name: str, finder_type: FinderType = "Dom_located"):
        return self._find_element(By.CLASS_NAME, class_name, finder_type)

    def find_element_by_xpath(self, xpath: str, finder_type: FinderType = "Dom_located"):
        return self._find_element(By.XPATH, xpath, finder_type)

    def find_element_by_css_selector(self, css_selector: str, finder_type: FinderType = "Dom_located"):
        return self._find_element(By.CSS_SELECTOR, css_selector, finder_type)

    def find_element_by_link_text(self, link_text: str, finder_type: FinderType = "Dom_located"):
        return self._find_element(By.LINK_TEXT, link_text, finder_type)

    def find_element_by_partial_link_text(self, partial_link_text: str, finder_type: FinderType = "Dom_located"):
        return self._find_element(By.PARTIAL_LINK_TEXT, partial_link_text, finder_type)

    def find_element_by_tag_name(self, tag_name: str, finder_type: FinderType = "Dom_located"):
        return self._find_element(By.TAG_NAME, tag_name, finder_type)

    def find_element_by_name(self, name: str, finder_type: FinderType = "Dom_located"):
        return self._find_element(By.NAME, name, finder_type)
