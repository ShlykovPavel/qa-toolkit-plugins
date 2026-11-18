from Appium.app_keys.screen_actions import ScreenActions


class BaseElements(ScreenActions):
    """Элементы, общие для всех экранов приложения.

    Не база для наследования (новые экраны наследуют ScreenActions),
    а готовый набор общих элементов — используется в модулях напрямую.
    """

    @property
    def exit_modal_button(self):
        """Кнопка закрытия модального окна («х»)."""
        return self.get_element("app_dialog_exit_button")

    @property
    def submit_button(self):
        """Кнопка подтверждения в модалках и формах."""
        return self.get_element("app_submit_button")
