create table if not exists raobai_channels (
    guild_id bigint primary key,
    channel_id bigint,
    guild_name text
);

create table if not exists bot_configs (
    key text primary key,
    value text
);

create table if not exists admins (
    user_id bigint primary key
);

create table if not exists roles (
    role_id bigint primary key
);

create table if not exists learned_responses (
    trigger text primary key,
    normalized_trigger text unique,
    response_text text not null,
    response_type text default 'text',
    match_type text default 'exact',
    priority integer default 100,
    enabled integer default 1,
    created_by bigint,
    usage_count integer default 0,
    last_used_at text,
    created_at text default to_char(now() at time zone 'UTC', 'YYYY-MM-DD HH24:MI:SS')
);

create table if not exists bot_actions (
    action_name text primary key,
    trigger text not null,
    normalized_trigger text not null,
    action_type text default 'message',
    payload text not null,
    match_type text default 'exact',
    priority integer default 100,
    enabled integer default 1,
    created_by bigint,
    usage_count integer default 0,
    last_used_at text,
    created_at text default to_char(now() at time zone 'UTC', 'YYYY-MM-DD HH24:MI:SS')
);

create table if not exists learning_queue (
    id bigint generated always as identity primary key,
    guild_id bigint,
    channel_id bigint,
    user_id bigint,
    username text,
    content text,
    normalized_content text,
    status text default 'pending',
    note text,
    created_at text default to_char(now() at time zone 'UTC', 'YYYY-MM-DD HH24:MI:SS')
);

create table if not exists conversation_memory (
    id bigint generated always as identity primary key,
    guild_id bigint,
    channel_id bigint,
    user_id bigint,
    role text,
    content text,
    created_at text default to_char(now() at time zone 'UTC', 'YYYY-MM-DD HH24:MI:SS')
);

create table if not exists scripts (
    name text primary key,
    content text
);

create table if not exists oauth_members (
    user_id text primary key,
    access_token text,
    refresh_token text
);

create table if not exists member_ids (
    user_id text primary key,
    guild_id text
);

create table if not exists users (
    user_id text primary key,
    access_token text,
    refresh_token text
);

create table if not exists accounts (
    id bigint generated always as identity primary key,
    guild_id bigint,
    description text,
    all_images text,
    timestamp text default to_char(now() at time zone 'UTC', 'YYYY-MM-DD HH24:MI:SS')
);
