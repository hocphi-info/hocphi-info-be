-- 000001_init (down)

BEGIN;

DROP VIEW IF EXISTS school_track_stats;

DROP TABLE IF EXISTS data_issue_reports;
DROP TABLE IF EXISTS post_grad_requirements;
DROP TABLE IF EXISTS program_increase;
DROP TABLE IF EXISTS tuition_records;
DROP TABLE IF EXISTS programs;
DROP TABLE IF EXISTS sources;
DROP TABLE IF EXISTS majors;
DROP TABLE IF EXISTS schools;
DROP TABLE IF EXISTS app_settings;
DROP TABLE IF EXISTS major_groups;
DROP TABLE IF EXISTS cities;

DROP TYPE IF EXISTS source_doc_type;
DROP TYPE IF EXISTS increase_source_type;
DROP TYPE IF EXISTS data_confidence;
DROP TYPE IF EXISTS tuition_unit;
DROP TYPE IF EXISTS program_track;
DROP TYPE IF EXISTS school_category;

DROP FUNCTION IF EXISTS set_updated_at();

COMMIT;
