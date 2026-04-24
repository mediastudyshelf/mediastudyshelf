.PHONY: all up down build

all:
	@echo "Options for running project"
	@echo

up:
	docker compose -f docker/docker-compose.yaml --profile=dev up

down:
	docker compose -f docker/docker-compose.yaml --profile=dev stop
	docker compose -f docker/docker-compose.yaml --profile=dev rm -f

build:
	docker build -t mediastudyshelf/mediastudyshelf -f docker/Dockerfile .