#!/bin/sh

autoflake -r ./starter --remove-all-unused-imports -i
isort -q ./starter
black -q ./starter
