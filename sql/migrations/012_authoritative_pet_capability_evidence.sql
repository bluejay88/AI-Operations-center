create table if not exists pet_capability_manifests (
    manifest_sha256 text primary key,
    manifest jsonb not null,
    created_at timestamptz not null default now(),
    constraint pet_capability_manifest_hash_format check (manifest_sha256 ~ '^[0-9a-f]{64}$'),
    constraint pet_capability_manifest_object check (jsonb_typeof(manifest) = 'object')
);

create table if not exists pet_capability_reviews (
    id bigserial primary key,
    manifest_sha256 text not null references pet_capability_manifests(manifest_sha256) on delete restrict,
    reviewer_id text not null,
    reviewer_role text not null check (reviewer_role in ('quality', 'security')),
    decision text not null check (decision in ('accepted', 'rejected', 'needs_changes')),
    rubric jsonb not null,
    evidence jsonb not null default '{}',
    created_at timestamptz not null default now(),
    check (jsonb_typeof(rubric) = 'object'),
    check (jsonb_typeof(evidence) = 'object')
);

create index if not exists idx_pet_capability_reviews_manifest_time
    on pet_capability_reviews(manifest_sha256, created_at, id);

create table if not exists pet_capability_brain_decisions (
    id bigserial primary key,
    manifest_sha256 text not null references pet_capability_manifests(manifest_sha256) on delete restrict,
    decision text not null check (decision in ('hold', 'canary_passed', 'release', 'rejected')),
    actor text not null,
    evidence jsonb not null default '{}',
    created_at timestamptz not null default now(),
    check (jsonb_typeof(evidence) = 'object')
);

create index if not exists idx_pet_capability_brain_decisions_manifest_time
    on pet_capability_brain_decisions(manifest_sha256, created_at desc, id desc);

create or replace function reject_pet_capability_authority_mutation()
returns trigger
language plpgsql
as $$
begin
    raise exception 'PET capability authority records are append-only'
        using errcode = '42501';
end;
$$;

drop trigger if exists pet_capability_manifests_append_only on pet_capability_manifests;
create trigger pet_capability_manifests_append_only
before update or delete on pet_capability_manifests
for each row execute function reject_pet_capability_authority_mutation();

drop trigger if exists pet_capability_reviews_append_only on pet_capability_reviews;
create trigger pet_capability_reviews_append_only
before update or delete on pet_capability_reviews
for each row execute function reject_pet_capability_authority_mutation();

drop trigger if exists pet_capability_brain_decisions_append_only on pet_capability_brain_decisions;
create trigger pet_capability_brain_decisions_append_only
before update or delete on pet_capability_brain_decisions
for each row execute function reject_pet_capability_authority_mutation();

revoke all on table pet_capability_manifests from public;
revoke all on table pet_capability_reviews from public;
revoke all on table pet_capability_brain_decisions from public;
revoke all on sequence pet_capability_reviews_id_seq from public;
revoke all on sequence pet_capability_brain_decisions_id_seq from public;
revoke execute on function reject_pet_capability_authority_mutation() from public;

comment on table pet_capability_manifests is
    'Immutable content-addressed certification manifests. The evaluator recomputes manifest_sha256 before trusting any reference.';
comment on table pet_capability_reviews is
    'Append-only authenticated-review records; evaluator requires separate accepted quality and security roles.';
comment on table pet_capability_brain_decisions is
    'Append-only Brain decisions bound to exactly one content-addressed manifest; the latest decision controls the release gate.';
