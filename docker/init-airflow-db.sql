-- Runs once when the Postgres volume is first created: a separate database
-- and role for Airflow's own metadata, kept apart from the pipeline data.
create role airflow with login password 'airflow';
create database airflow owner airflow;
