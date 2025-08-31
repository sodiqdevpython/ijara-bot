#!/bin/sh

echo "Migratsiyalar uchun bu..."
python manage.py migrate --noinput

echo "Statik fayllar..."
python manage.py collectstatic --noinput

exec "$@"
