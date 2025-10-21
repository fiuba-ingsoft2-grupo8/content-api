SHELL := /bin/bash
PWD := $(shell pwd)

all:

build-system:
	docker build -f ./Dockerfile -t "content-api:latest" .
.PHONY: build-system

up-local: build-system
	docker compose -f docker-compose-local.yaml up -d --build --remove-orphans
.PHONY: up

up-remote: build-system
	docker compose -f docker-compose-remote.yaml up -d --build --remove-orphans
.PHONY: up-remote-db

down-local:
	docker compose -f docker-compose-local.yaml down
.PHONY: down-local

down-remote:
	docker compose -f docker-compose-remote.yaml down
.PHONY: down-remote

test:
	python -m pytest --cov=src --cov-report=xml tests/ -v
.PHONY: test

test3:
	python3 -m pytest --cov=src --cov-report=xml tests/ -v
.PHONY: test3