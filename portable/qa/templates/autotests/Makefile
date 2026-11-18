# Цели — не файлы: без .PHONY цель молчит, если рядом лежит папка с тем же именем.
.PHONY: verify smoke regression report

# Максимальная проверка без живого стенда: синтаксис + импорты + фикстуры
# + механические запреты конвенций (слепые паузы — scripts/check_no_sleep.py)
verify:
	python3 -m compileall -q config.py logger.py src Tests
# слой: mobile
	python3 -m compileall -q Appium
# /слой
# слой: frontend
	python3 -m compileall -q frontend
# /слой
	python3 scripts/check_no_sleep.py
	.venv/bin/python -m pytest --collect-only -q

smoke:
	pytest -v -m smoke --alluredir=testresults/ Tests/Smoke_tests

regression:
	pytest -v -m regression --alluredir=testresults/ Tests/Regression_tests

# слой: mobile
.PHONY: mobile
mobile:
	pytest -v -m mobile --alluredir=testresults/ Tests/Mobile_tests

# /слой
# слой: frontend
.PHONY: frontend
frontend:
	pytest -v -m frontend --alluredir=testresults/ Tests/Frontend_tests

# /слой

report:
	allure generate --single-file testresults/ -o allure-report --clean
	open allure-report/index.html
