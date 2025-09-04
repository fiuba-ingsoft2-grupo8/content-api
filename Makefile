SHELL := /bin/bash
PWD := $(shell pwd)

all:

build-system:
	docker build -f ./Dockerfile -t "content-api:latest" .
.PHONY: build-system

up-local: build-system
	docker compose -f docker-compose-full-local.yaml up -d --build --remove-orphans
.PHONY: up

up-remote: build-system
	docker compose -f docker-compose-remote-db.yaml up -d --build --remove-orphans
.PHONY: up-remote-db

down-local:
	docker compose -f docker-compose-full-local.yaml down
.PHONY: down-local

down-remote:
	docker compose -f docker-compose-remote-db.yaml down
.PHONY: down-remote

test:
	python -m pytest tests/test_main.py -v
.PHONY: test