-- Code lists published by HM Land Registry.
create schema if not exists ppd;

create table ppd.ref_property_type (
    code   char(1)     primary key,
    label  text        not null unique
);

create table ppd.ref_tenure (
    code   char(1)     primary key,
    label  text        not null unique
);

create table ppd.ref_ppd_category (
    code   char(1)     primary key,
    label  text        not null unique,
    note   text
);

insert into ppd.ref_property_type (code, label) values
    ('D', 'Detached'), ('S', 'Semi-detached'), ('T', 'Terraced'),
    ('F', 'Flat/maisonette'), ('O', 'Other');

insert into ppd.ref_tenure (code, label) values
    ('F', 'Freehold'), ('L', 'Leasehold'), ('U', 'Unknown');

insert into ppd.ref_ppd_category (code, label, note) values
    ('A', 'Standard', 'Sale at full market value to a private individual'),
    ('B', 'Additional', 'Repossessions, buy-to-lets and sales to non-private individuals');
