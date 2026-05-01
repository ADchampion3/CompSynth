# Agent Notes

## Project Stage

This project is still in an early development stage. Do not spend effort on backward-compatible SQLite migrations or preserving compatibility with old local database files unless the user explicitly asks for it.

For now, schema changes may assume a fresh local database. Keep the schema bootstrap simple and prefer deleting/recreating local development data over adding compatibility code.
