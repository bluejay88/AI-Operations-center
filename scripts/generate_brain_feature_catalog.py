"""Generate the auditable 500-capability Brain PC ledger and migration 009."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from generate_pet_feature_catalog import canonical_json, parse_source


ROOT = Path(__file__).resolve().parents[1]


def build_artifact(source_text: str) -> dict[str, object]:
    normalized = source_text.replace("\r\n", "\n").replace("\r", "\n")
    source_rows = parse_source(normalized)
    rows: list[dict[str, object]] = []
    for source in source_rows:
        feature_id = str(source["feature_id"]).replace("PET-", "BRAIN-", 1)
        sensitivity = source["sensitivity"]
        acceptance = {
            "criteria_id": f"{feature_id}-AC-01",
            "statement": f"Brain PC demonstrates the authorized capability: {source['source_title']}",
            "required_evidence": ["test_result", "audit_report", "brain_listener_receipt"],
            "required_reviews": ["quality", "security"] if sensitivity != "standard" else ["quality"],
            "prohibits_self_approval": True,
        }
        implementation_contract = {
            "feature_id": feature_id,
            "source_pet_feature_id": source["feature_id"],
            "source_title": source["source_title"],
            "execution_authority": "brain-gaming-pc",
            "initial_implementation_status": "not_started",
        }
        evidence_requirements = {
            "minimum_artifacts": 3,
            "required_types": acceptance["required_evidence"],
            "content_hash_required": True,
            "physical_brain_correlation_required": True,
        }
        version_content = {
            "implementation_contract": implementation_contract,
            "acceptance_criteria": acceptance,
            "acceptance_schema": {
                "type": "object",
                "required": ["artifacts", "tests", "audit", "listener_event_id"],
                "properties": {
                    "artifacts": {"type": "array", "minItems": 1},
                    "tests": {"type": "object"},
                    "audit": {"type": "object"},
                    "listener_event_id": {"type": "integer", "minimum": 1},
                },
            },
            "evidence_requirements": evidence_requirements,
            "failure_modes": {
                "missing_evidence": "remain_planned",
                "failed_review": "rejected",
                "stale_verification": "gated",
            },
        }
        rows.append(
            {
                "feature_id": feature_id,
                "source_pet_feature_id": source["feature_id"],
                "domain_no": source["domain_no"],
                "item_no": source["item_no"],
                "source_order": source["source_order"],
                "domain_title": implementation_contract["source_title"] if False else "",
                "source_title": source["source_title"],
                "sensitivity": sensitivity,
                "default_owner_role": "brain-orchestrator",
                "version": 1,
                **version_content,
                "content_sha256": hashlib.sha256(canonical_json(version_content).encode("utf-8")).hexdigest(),
            }
        )
    # Domain headings are deliberately derived separately from titles so source capability text stays exact.
    headings = {
        1: "Core Identity and Personality", 2: "Brain Communication", 3: "Local Conversation Abilities",
        4: "Desktop Assistance", 5: "File and Folder Management", 6: "Document Creation",
        7: "Spreadsheet and Data Abilities", 8: "Research and Knowledge Work", 9: "Creative Design Abilities",
        10: "Video and Audio Abilities", 11: "Website Creation and Management", 12: "Customer Service",
        13: "Sales and Lead Management", 14: "Order Fulfillment", 15: "Finance and Business Monitoring",
        16: "Marketing Automation", 17: "Security and Privacy", 18: "Quality Assurance and Checks",
        19: "Device Health and Maintenance", 20: "Advanced Autonomy and Intelligence",
    }
    for row in rows:
        row["domain_title"] = headings[int(row["domain_no"])]
    base_keys = (
        "feature_id", "source_pet_feature_id", "domain_no", "item_no", "source_order", "domain_title",
        "source_title", "sensitivity", "default_owner_role",
    )
    catalog_hash = hashlib.sha256(canonical_json([{k: row[k] for k in base_keys} for row in rows]).encode("utf-8")).hexdigest()
    return {
        "schema_version": 1,
        "catalog_id": "brain-feature-catalog-v1",
        "expected_total": 500,
        "source_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        "catalog_sha256": catalog_hash,
        "features": rows,
    }


def q(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def build_migration(artifact: dict[str, object]) -> str:
    payload = canonical_json(artifact["features"])
    source_hash = artifact["source_sha256"]
    catalog_hash = artifact["catalog_sha256"]
    return f"""-- Generated by scripts/generate_brain_feature_catalog.py; do not hand-edit.
-- Source SHA-256: {source_hash}
-- Catalog SHA-256: {catalog_hash}

create table if not exists brain_feature_catalog_sources (
    catalog_id text primary key,
    schema_version integer not null check (schema_version > 0),
    expected_total integer not null check (expected_total = 500),
    source_sha256 char(64) not null check (source_sha256 ~ '^[0-9a-f]{{64}}$'),
    catalog_sha256 char(64) not null check (catalog_sha256 ~ '^[0-9a-f]{{64}}$'),
    created_at timestamptz not null default now()
);

create table if not exists brain_feature_definitions (
    feature_id text primary key check (feature_id ~ '^BRAIN-(0[1-9]|1[0-9]|20)-(0[1-9]|1[0-9]|2[0-5])$'),
    source_pet_feature_id text not null unique check (source_pet_feature_id ~ '^PET-(0[1-9]|1[0-9]|20)-(0[1-9]|1[0-9]|2[0-5])$'),
    domain_no smallint not null check (domain_no between 1 and 20),
    item_no smallint not null check (item_no between 1 and 25),
    source_order smallint not null unique check (source_order between 1 and 500),
    domain_title text not null check (btrim(domain_title) <> ''),
    source_title text not null check (btrim(source_title) <> ''),
    sensitivity text not null check (sensitivity in ('standard', 'elevated', 'high')),
    default_owner_role text not null check (btrim(default_owner_role) <> ''),
    created_at timestamptz not null default now(),
    retired_at timestamptz,
    unique (domain_no, item_no),
    check (feature_id = format('BRAIN-%s-%s', lpad(domain_no::text, 2, '0'), lpad(item_no::text, 2, '0'))),
    check (source_pet_feature_id = format('PET-%s-%s', lpad(domain_no::text, 2, '0'), lpad(item_no::text, 2, '0'))),
    check (source_order = ((domain_no - 1) * 25 + item_no))
);

create table if not exists brain_feature_versions (
    id bigserial primary key,
    feature_id text not null references brain_feature_definitions(feature_id) on delete restrict,
    version integer not null check (version > 0),
    implementation_contract jsonb not null check (jsonb_typeof(implementation_contract) = 'object'),
    acceptance_criteria jsonb not null check (jsonb_typeof(acceptance_criteria) = 'object'),
    acceptance_schema jsonb not null check (jsonb_typeof(acceptance_schema) = 'object'),
    evidence_requirements jsonb not null check (jsonb_typeof(evidence_requirements) = 'object'),
    failure_modes jsonb not null check (jsonb_typeof(failure_modes) = 'object'),
    content_sha256 char(64) not null check (content_sha256 ~ '^[0-9a-f]{{64}}$'),
    created_by text not null check (btrim(created_by) <> ''),
    created_at timestamptz not null default now(),
    supersedes_version integer,
    unique (feature_id, version), unique (feature_id, content_sha256),
    foreign key (feature_id, supersedes_version) references brain_feature_versions(feature_id, version) on delete restrict,
    check (supersedes_version is null or supersedes_version < version)
);

create table if not exists brain_feature_state_current (
    feature_id text primary key,
    feature_version integer not null,
    state char(1) not null check (state in ('P','G','O','R')),
    implementation_status text not null check (implementation_status in ('not_started','in_progress','implemented','blocked')),
    evidence_status text not null check (evidence_status in ('none','submitted','verified','rejected')),
    release_status text not null check (release_status in ('unreleased','gated','operational','rejected')),
    implementation_ref text,
    evidence_manifest_sha256 char(64) check (evidence_manifest_sha256 is null or evidence_manifest_sha256 ~ '^[0-9a-f]{{64}}$'),
    release_id bigint,
    last_verified_at timestamptz,
    verification_expires_at timestamptz,
    row_version bigint not null default 1 check (row_version > 0),
    updated_at timestamptz not null default now(),
    foreign key (feature_id, feature_version) references brain_feature_versions(feature_id, version) on delete restrict,
    check (state <> 'O' or (implementation_status = 'implemented' and evidence_status = 'verified' and release_status = 'operational'
          and implementation_ref is not null and evidence_manifest_sha256 is not null and release_id is not null and last_verified_at is not null)),
    check (verification_expires_at is null or (last_verified_at is not null and verification_expires_at > last_verified_at))
);

create table if not exists brain_feature_state_events (
    id bigserial primary key,
    feature_id text not null,
    feature_version integer not null,
    from_state char(1) check (from_state is null or from_state in ('P','G','O','R')),
    to_state char(1) not null check (to_state in ('P','G','O','R')),
    implementation_status text not null check (implementation_status in ('not_started','in_progress','implemented','blocked')),
    evidence_status text not null check (evidence_status in ('none','submitted','verified','rejected')),
    release_status text not null check (release_status in ('unreleased','gated','operational','rejected')),
    implementation_ref text,
    evidence_manifest_sha256 char(64),
    release_id bigint,
    actor text not null check (btrim(actor) <> ''),
    reason text not null check (btrim(reason) <> ''),
    idempotency_key text not null unique check (btrim(idempotency_key) <> ''),
    created_at timestamptz not null default now(),
    foreign key (feature_id, feature_version) references brain_feature_versions(feature_id, version) on delete restrict
);

create index if not exists idx_brain_feature_state_status_updated on brain_feature_state_current(state, implementation_status, updated_at desc);
create index if not exists idx_brain_feature_state_evidence on brain_feature_state_current(evidence_status, release_status, updated_at desc);
create index if not exists idx_brain_feature_state_expiry on brain_feature_state_current(verification_expires_at) where verification_expires_at is not null;
create index if not exists idx_brain_feature_definitions_domain_order on brain_feature_definitions(domain_no, source_order);
create index if not exists idx_brain_feature_events_feature_time on brain_feature_state_events(feature_id, created_at desc, id desc);

create or replace function reject_brain_feature_immutable_mutation() returns trigger language plpgsql as $$
begin raise exception '% is append-only/immutable', tg_table_name; end; $$;
drop trigger if exists trg_brain_feature_definitions_immutable on brain_feature_definitions;
create trigger trg_brain_feature_definitions_immutable before update or delete on brain_feature_definitions for each row execute function reject_brain_feature_immutable_mutation();
drop trigger if exists trg_brain_feature_versions_immutable on brain_feature_versions;
create trigger trg_brain_feature_versions_immutable before update or delete on brain_feature_versions for each row execute function reject_brain_feature_immutable_mutation();
drop trigger if exists trg_brain_feature_events_immutable on brain_feature_state_events;
create trigger trg_brain_feature_events_immutable before update or delete on brain_feature_state_events for each row execute function reject_brain_feature_immutable_mutation();
drop trigger if exists trg_brain_feature_sources_immutable on brain_feature_catalog_sources;
create trigger trg_brain_feature_sources_immutable before update or delete on brain_feature_catalog_sources for each row execute function reject_brain_feature_immutable_mutation();

create or replace function guard_brain_feature_current_mutation() returns trigger language plpgsql as $$
begin
    if current_setting('aiops.brain_feature_transition', true) is distinct from 'allowed' then
        raise exception 'brain_feature_state_current may only change through transition_brain_feature_state';
    end if;
    return new;
end; $$;
drop trigger if exists trg_brain_feature_current_guard on brain_feature_state_current;
create trigger trg_brain_feature_current_guard before update or delete on brain_feature_state_current for each row execute function guard_brain_feature_current_mutation();

create or replace function seed_brain_feature_catalog_v1()
returns table(inserted_definitions bigint, inserted_versions bigint, inserted_states bigint, inserted_events bigint)
language plpgsql as $seed$
declare catalog jsonb := $catalog${payload}$catalog$::jsonb;
begin
    insert into brain_feature_catalog_sources(catalog_id,schema_version,expected_total,source_sha256,catalog_sha256)
    values ('brain-feature-catalog-v1',1,500,{q(source_hash)},{q(catalog_hash)}) on conflict (catalog_id) do nothing;
    if not exists (select 1 from brain_feature_catalog_sources where catalog_id='brain-feature-catalog-v1' and schema_version=1
      and expected_total=500 and source_sha256={q(source_hash)} and catalog_sha256={q(catalog_hash)}) then
        raise exception 'Brain catalog source/hash mismatch';
    end if;

    insert into brain_feature_definitions(feature_id,source_pet_feature_id,domain_no,item_no,source_order,domain_title,source_title,sensitivity,default_owner_role)
    select e->>'feature_id',e->>'source_pet_feature_id',(e->>'domain_no')::smallint,(e->>'item_no')::smallint,
      (e->>'source_order')::smallint,e->>'domain_title',e->>'source_title',e->>'sensitivity',e->>'default_owner_role'
    from jsonb_array_elements(catalog) e on conflict (feature_id) do nothing;
    get diagnostics inserted_definitions = row_count;
    if exists (select 1 from jsonb_array_elements(catalog) e left join brain_feature_definitions d on d.feature_id=e->>'feature_id'
      where d.feature_id is null or d.source_pet_feature_id<>e->>'source_pet_feature_id' or d.domain_no<>(e->>'domain_no')::smallint
      or d.item_no<>(e->>'item_no')::smallint or d.source_order<>(e->>'source_order')::smallint or d.domain_title<>e->>'domain_title'
      or d.source_title<>e->>'source_title' or d.sensitivity<>e->>'sensitivity' or d.default_owner_role<>e->>'default_owner_role') then
        raise exception 'Brain catalog definition mismatch; immutable source was altered';
    end if;

    insert into brain_feature_versions(feature_id,version,implementation_contract,acceptance_criteria,acceptance_schema,evidence_requirements,
      failure_modes,content_sha256,created_by,supersedes_version)
    select e->>'feature_id',1,e->'implementation_contract',e->'acceptance_criteria',e->'acceptance_schema',e->'evidence_requirements',
      e->'failure_modes',e->>'content_sha256','brain-feature-catalog-v1',null from jsonb_array_elements(catalog) e
    on conflict (feature_id,version) do nothing;
    get diagnostics inserted_versions = row_count;
    if exists (select 1 from jsonb_array_elements(catalog) e left join brain_feature_versions v on v.feature_id=e->>'feature_id' and v.version=1
      where v.id is null or v.implementation_contract<>e->'implementation_contract' or v.acceptance_criteria<>e->'acceptance_criteria'
      or v.acceptance_schema<>e->'acceptance_schema' or v.evidence_requirements<>e->'evidence_requirements'
      or v.failure_modes<>e->'failure_modes' or v.content_sha256<>e->>'content_sha256') then
        raise exception 'Brain catalog version mismatch; immutable contract was altered';
    end if;

    insert into brain_feature_state_current(feature_id,feature_version,state,implementation_status,evidence_status,release_status,row_version)
    select e->>'feature_id',1,'P','not_started','none','unreleased',1 from jsonb_array_elements(catalog) e
    on conflict (feature_id) do nothing;
    get diagnostics inserted_states = row_count;
    insert into brain_feature_state_events(feature_id,feature_version,from_state,to_state,implementation_status,evidence_status,release_status,
      actor,reason,idempotency_key)
    select e->>'feature_id',1,null,'P','not_started','none','unreleased','brain-feature-catalog-v1','Initial catalog state',
      'brain-feature-catalog-v1:'||(e->>'feature_id')||':initial' from jsonb_array_elements(catalog) e
    on conflict (idempotency_key) do nothing;
    get diagnostics inserted_events = row_count;
    if (select count(*) from brain_feature_definitions)<>500 or (select count(*) from brain_feature_versions where version=1)<>500
      or (select count(*) from brain_feature_state_current)<>500
      or (select count(*) from brain_feature_state_events where actor='brain-feature-catalog-v1')<>500 then
        raise exception 'Brain catalog integrity failure: expected exactly 500 definitions, versions, states, and initial events';
    end if;
    return next;
end; $seed$;

create or replace function transition_brain_feature_state(
    p_feature_id text,p_expected_row_version bigint,p_to_state char(1),p_implementation_status text,p_evidence_status text,
    p_release_status text,p_actor text,p_reason text,p_idempotency_key text,p_implementation_ref text default null,
    p_evidence_manifest_sha256 char(64) default null,p_release_id bigint default null,p_last_verified_at timestamptz default null,
    p_verification_expires_at timestamptz default null)
returns brain_feature_state_current language plpgsql as $$
declare current_row brain_feature_state_current%rowtype; prior brain_feature_state_events%rowtype;
begin
    select * into prior from brain_feature_state_events where idempotency_key=p_idempotency_key;
    if found then
      if prior.feature_id<>p_feature_id or prior.to_state<>p_to_state or prior.implementation_status<>p_implementation_status
        or prior.evidence_status<>p_evidence_status or prior.release_status<>p_release_status or prior.actor<>p_actor or prior.reason<>p_reason then
          raise exception 'Brain transition idempotency key reused with different content';
      end if;
      select * into current_row from brain_feature_state_current where feature_id=p_feature_id; return current_row;
    end if;
    select * into current_row from brain_feature_state_current where feature_id=p_feature_id for update;
    if not found then raise exception 'Unknown Brain feature %',p_feature_id; end if;
    if current_row.row_version<>p_expected_row_version then raise exception 'Brain feature row version conflict'; end if;
    if p_to_state='O' and not (p_implementation_status='implemented' and p_evidence_status='verified' and p_release_status='operational'
      and p_implementation_ref is not null and p_evidence_manifest_sha256 is not null and p_release_id is not null and p_last_verified_at is not null) then
        raise exception 'Operational Brain feature requires implementation, verified evidence, release, and verification';
    end if;
    insert into brain_feature_state_events(feature_id,feature_version,from_state,to_state,implementation_status,evidence_status,release_status,
      implementation_ref,evidence_manifest_sha256,release_id,actor,reason,idempotency_key)
    values(current_row.feature_id,current_row.feature_version,current_row.state,p_to_state,p_implementation_status,p_evidence_status,p_release_status,
      p_implementation_ref,p_evidence_manifest_sha256,p_release_id,p_actor,p_reason,p_idempotency_key);
    perform set_config('aiops.brain_feature_transition','allowed',true);
    update brain_feature_state_current set state=p_to_state,implementation_status=p_implementation_status,evidence_status=p_evidence_status,
      release_status=p_release_status,implementation_ref=p_implementation_ref,evidence_manifest_sha256=p_evidence_manifest_sha256,
      release_id=p_release_id,last_verified_at=p_last_verified_at,verification_expires_at=p_verification_expires_at,
      row_version=row_version+1,updated_at=now() where feature_id=p_feature_id returning * into current_row;
    return current_row;
end; $$;

create or replace view brain_feature_state_summary as
select count(*) filter(where state='O')::integer operational,count(*) filter(where state='G')::integer gated,
  count(*) filter(where state='P')::integer planned,count(*) filter(where state='R')::integer rejected,count(*)::integer total,
  500::integer expected_total,(count(*)=500)::boolean integrity,
  count(*) filter(where implementation_status='implemented')::integer implemented,
  count(*) filter(where evidence_status='verified')::integer evidence_verified,
  count(*) filter(where release_status='operational')::integer released_operational
from brain_feature_state_current;

select * from seed_brain_feature_catalog_v1();
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--artifact", type=Path, default=ROOT / "config" / "brain_feature_catalog_v1.json")
    parser.add_argument("--migration", type=Path, default=ROOT / "sql" / "migrations" / "009_brain_feature_catalog.sql")
    args = parser.parse_args()
    artifact = build_artifact(args.source.read_text(encoding="utf-8"))
    args.artifact.write_text(json.dumps(artifact,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8",newline="\n")
    args.migration.write_text(build_migration(artifact),encoding="utf-8",newline="\n")
    print(f"generated {len(artifact['features'])} Brain features")


if __name__ == "__main__": main()
