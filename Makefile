.PHONY: all up down

all:
	@echo "Options for running project"
	@echo

up:
	docker compose --profile=dev up

down:
	docker compose --profile=dev stop
	docker compose --profile=dev rm -f