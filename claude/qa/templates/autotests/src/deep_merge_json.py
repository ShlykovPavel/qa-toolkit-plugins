from typing import Dict, Any


def deep_merge(dict1: Dict[Any, Any], dict2: Dict[Any, Any]) -> Dict[Any, Any]:
    """
    Выполняет глубокое слияние двух словарей, где dict2 перезаписывает или дополняет значения dict1.
    Поддерживает вложенные словари и списки словарей (для списков обновляется первый словарь).
    Создаёт новый словарь, не изменяя входные.

    Args:
        dict1: Базовый словарь, содержащий исходные данные.
        dict2: Словарь с обновлениями, которые перезаписывают или дополняют dict1.

    Returns:
        Dict[Any, Any]: Новый словарь, содержащий объединённые данные.

    Examples:
        # Обновление простого значения
        >>> dict1 = {"a": 1}
        >>> dict2 = {"a": 2}
        >>> deep_merge(dict1, dict2)
        {'a': 2}

        # Обновление элемента во вложенном словаре
        >>> dict1 = {"b": {"x": 10, "y": 20}}
        >>> dict2 = {"b": {"y": 30}}
        >>> deep_merge(dict1, dict2)
        {'b': {'x': 10, 'y': 30}}

        # Обновление элемента во вложенном массиве словарей
        >>> dict1 = {"sections": [{"sectionId": None, "canDelete": False}]}
        >>> dict2 = {"sections": {"sectionId": 84}}
        >>> deep_merge(dict1, dict2)
        {'sections': [{'sectionId': 84, 'canDelete': False}]}

    Notes:
        - Для обновления элемента во вложенном словаре передайте в dict2 словарь с той же структурой ключа.
          Например, чтобы обновить meta в словаре "meta": {"iconColor": None,"iconPath": "img/svg/Office_and_Editing/FilePy_Fill.svg"}  используй meta={"iconColor": "HUY"}
        - Для обновления элемента во вложенном массиве словарей передайте в dict2 словарь, который обновит
          первый словарь в списке. Например, чтобы обновить 'sectionId' в
          {"sections": [{"sectionId": None, "canDelete": False}]}, используйте
          sections={"sectionId": user_data_admin['form_unit_section_id']}.
        - Если список в dict1 пустой или не содержит словарей, значение из dict2 заменит его полностью.
    """
    result = dict1.copy()
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        elif key in result and isinstance(result[key], list) and isinstance(value, dict):
            if len(result[key]) > 0 and isinstance(result[key][0], dict):
                result[key] = [deep_merge(result[key][0], value)]
            else:
                result[key] = value
        else:
            result[key] = value
    return result
