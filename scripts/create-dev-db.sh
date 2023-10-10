DB_FILE=energy_assistant.db
if [ -f "$DB_FILE" ]; then
    echo "$DB_FILE already exists. In case you want to create a empty db, delete the $DB_FILE first."
else
    echo "Generating or upgrading /data/$DB_FILE"
    alembic upgrade head
    cp "/data/$DB_FILE" .
fi
