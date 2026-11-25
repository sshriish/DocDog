-- Paste into Neon -> SQL Editor and run once.
create table if not exists users(
  id uuid primary key default gen_random_uuid(),
  email text unique not null, name text default '',
  password_hash text not null, created_at timestamptz default now());
create table if not exists projects(
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references users(id) on delete cascade,
  name text not null, description text default '',
  created_at timestamptz default now(), unique(owner_id, name));
create table if not exists documents(
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  uploader_id uuid not null references users(id),
  filename text not null, file_type text not null, size_bytes bigint not null,
  checksum text not null,
  status text not null check (status in ('succeeded','failed','unsupported')),
  error text, created_at timestamptz default now());
create index if not exists ix_docs_project on documents(project_id);
create index if not exists ix_docs_checksum on documents(checksum);
create table if not exists document_files(
  document_id uuid primary key references documents(id) on delete cascade,
  data bytea not null);
create table if not exists document_content(
  document_id uuid primary key references documents(id) on delete cascade,
  extracted_text text default '', structure jsonb,
  search_vector tsvector generated always as (to_tsvector('english', coalesce(extracted_text,''))) stored);
create index if not exists ix_content_fts on document_content using gin(search_vector);
